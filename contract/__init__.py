import re
import math
from rpctools import rpc_factory
from ethereum.abi import ContractTranslator

ETH_ADDR = re.compile('^0x[0-9a-fA-F]{40}$')
MAX_GAS = int(math.pi*1.5*1e6)


class ContractError(Exception): pass


class Contract(object):
    """A base class for interacting with Ethereum contracts."""
    def __init__(self, address, interface, rpc_address, sender=None, gas=MAX_GAS):
        """Create a new Contract instance. Batch requests not supported!

        :param address: The address of the smart contract you want to use.
        :param interface: The full signature of the smart contract.
        :param rpc_address: The address of the RPC server for your Ethereum node.
        :param sender: The address to send from. If None, the default sender for your node is used.
        :param gas:  The maximum amount of gass to use per transaction/call.

        :type address: str
        :type interface: dict
        :type rpc_address: str
        :type sender: Optional[str]
        :type gas: int
        """
        err_fmt = 'Invalid {} address, must be 40 digit hex starting with \'0x\': {!r}'

        if not ETH_ADDR.match(address):
            raise ContractError(err_fmt.format('contract', address))

        self.translator = ContractTranslator(interface)
        self.rpc_client = rpc_factory(rpc_address, False)
        self.common_params = {'to': address, 'gas': hex(gas)}

        if sender is None:
            pass
        elif ETH_ADDR.match(sender):
            self.common_params['from'] = sender
        else:
            raise ContractError(err_fmt.format('sender', sender))

        def proxy_factory(name):
            # Generates proxy functions that use rpc methods under the hood.
            pyname = name.split('(')[0]  # a python compatible name

            def proxy(*args, **kwds):
                """Calls function {} in contract {}.

                If the optional `call` keyword is True, then the result of the function call
                is decoded into a Python object and returned, otherwise the transaction hash
                is returned.
                """
                tx = self.common_params.copy()
                data = self.translator.encode_function_call(pyname, args)
                tx['data'] = '0x{}'.format(data.encode('hex'))
                if kwds.get('call', False):
                    return self._call(pyname, tx)
                else:
                    return self._send(tx)

            proxy.__name__ = pyname
            proxy.__doc__ = proxy.__doc__.format(name, address)
            return proxy

        for item in interface:
            if item['type'] == 'function':
                proxy = proxy_factory(item['name'])
                if hasattr(self, proxy.__name__):
                    raise ContractError('Polymorphism not supported!')
                setattr(self, proxy.__name__, proxy)

    def _call(self, func_name, tx):
        # Uses call to interact with a contract.
        response = self.rpc_client.eth_call(tx, 'latest')
        self._check_response(response)
        raw_result = response['result'].lstrip('0x').decode('hex')
        return self.translator.decode(func_name, raw_result)

    def _send(self, tx):
        response = self.rpc_client.eth_sendTransaction(tx)
        self._check_response(response)
        return response['result']

    @staticmethod
    def _check_response(response):
        error_msg = 'error response from RPC server: {}'
        if 'error' in response:
            raise ContractError(error_msg.format(response))
