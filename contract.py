import re
import rlp
from ethereum.abi import ContractTranslator
from ethereum.transactions import Transaction
from ethereum.utils import privtoaddr, denoms

MAX_GAS = 0x4712388
ETH_ADDR = re.compile('^0x[0-9a-fA-F]{40}$')


def _hex2int(hx):
    return int(hx[2:], 16)


class ContractError(Exception): pass


class BaseContract(object):
    """A base class for interacting with Ethereum contracts."""
    def __init__(self, address, interface, rpc_client, sender, gas):
        """Arguments:
            address -- The address of the contract in hex, i.e. a string
                        containing '0x' followed by 40 hex digits.
            interface -- The full signature of the contract as a dictionary.
            rpc_client -- An RPC client from rpctools, connected to an Ethereum node.
            gas -- The default amount of gas to send in a transaction, as an int.

        Note: Contracts don't support RPC batching.
        """

        err_fmt = 'Invalid {} address, must be 40 digit hex starting with \'0x\': {!r}'

        if not ETH_ADDR.match(address):
            raise ContractError(err_fmt.format('contract', address))

        if not ETH_ADDR.match(sender):
            raise ContractError(err_fmt.format('sender', sender))

        self.address = address
        self.translator = ContractTranslator(interface)
        self.rpc_client = rpc_client
        self.sender = sender
        self.default_gas = gas
        self.default_gas_hex = hex(gas)

        def proxy_factory(func_name):
            # Generates proxy functions that use rpc methods under the hood.
            def proxy(*args, **kwds):
                """Calls the {!r} function in contract {}."""
                data = self.translator.encode_function_call(func_name, args)
                if kwds.get('call', False):
                    return self._call_dispatcher(func_name, data)
                else:
                    return self._send_dispatcher(data)
            proxy.__name__ = func_name
            proxy.__doc__ = proxy.__doc__.format(func_name, self.address)
            return proxy

        for item in interface:
            if item['type'] == 'function':
                name = item['name']
                setattr(self, name, proxy_factory(name))

    def _call_dispatcher(self, func_name, data):
        # Uses call to interact with a contract
        tx = {'to': self.address,
              'from': self.sender,
              'data': data,
              'gas': self.default_gas_hex}
        response = self.rpc_client.eth_call(tx, 'latest')
        raw_result = response['result'].lstrip('0x').decode('hex')
        return self.translator.decode(func_name, raw_result)

    def _send_dispatcher(self, data):
        """Sends Ethereum ABI encoded function calls to the contract."""
        raise NotImplementedError('_send_dispatcher must be implemented in a subclass!')


class LocalContract(BaseContract):
    """A class for interacting with Ethereum smart contracts through a local node."""
    def __init__(self, address, interface, rpc_client, sender, gas=MAX_GAS):
        BaseContract.__init__(self, address, interface, rpc_client, sender, gas)

    def _send_dispatcher(self, data):
        # Uses eth_sendTransaction to interact with a contract through a local Ethereum node.
        tx = {'to': self.address,
              'from': self.sender,
              'data': data,
              'gas': self.default_gas_hex}
        return self.rpc_client.eth_sendTransaction(tx)


class PublicContract(BaseContract):
    """A class for interacting with Ethereum smart contracts on a public node."""
    def __init__(self, address, interface, rpc_client, private_key, gas=MAX_GAS):
        if isinstance(private_key, (int, long)):
            private_key = hex(private_key)[2:].decode('hex').rjust(32, '\x00')
        elif not isinstance(private_key, str) or not len(private_key)==32:
            raise ContractError('private key bust be 32 byte bin encoded!')

        sender = '0x' + privtoaddr(private_key).encode('hex')

        BaseContract.__init__(self, address, interface, rpc_client, sender, gas)

        self.address_bin = address.lstrip('0x').decode('hex')
        self.private_key = private_key
        self.gas_price = 20 * denoms.shannon

    def _send_dispatcher(self, data):
        # Uses eth_sendRawTransaction to interact with contracts.
        nonce = _hex2int(self.rpc_client.eth_getTransactionCount(self.sender)['result'])
        tx = Transaction(nonce, self.gas_price, self.default_gas, self.address_bin, 0, data)
        raw_tx = '0x' + rlp.encode(tx.sign(self.private_key)).encode('hex')
        return self.eth_sendRawTransaction(raw_tx)['result']
