from azure.identity import DefaultAzureCredential
from azure.keyvault.keys import KeyClient
import os
import config
import util
import sys

from azure.keyvault import KeyVaultClient, KeyVaultAuthentication
from azure.common.credentials import ServicePrincipalCredentials
from web3 import Web3, HTTPProvider
from ethtoken.abi import EIP20_ABI
import secp256k1
from eth_account.internal.transactions import encode_transaction, serializable_unsigned_transaction_from_dict
from eth_keys import KeyAPI


def auth_callback(server, resource, scope):
    credentials = ServicePrincipalCredentials(
        client_id=config.CLIENT_ID,
        secret=config.PASSWORD,
        tenant=config.TENANT_ID,
        resource='https://vault.azure.net'
    )
    token = credentials.token
    return token['token_type'], token['access_token']

def sign_keyvault(addressSigner, signingClient, vault_url, key_name, key_version, tx, chain_id=0):
    unsigned_tx = serializable_unsigned_transaction_from_dict(tx)
    unsigned_tx_hash = unsigned_tx.hash()
    valid = False
    while not valid:
        sig_resp = signingClient.sign(vault_url, key_name, key_version, 'ES256K', unsigned_tx_hash)
        v, r, s, valid = util.convert_azure_secp256k1_signature_to_vrs(pubkey, unsigned_tx_hash, sig_resp.result, chain_id)

    vrs = (v,r,s)
    print("v, r, s: ", vrs)
    ret_signed_transaction = encode_transaction(unsigned_tx, vrs)
    return address_signer, ret_signed_transaction

#Find how not to set on environment
if __name__ == "__main__":
    repetitions = int(sys.argv[1])
    destination = sys.argv[2]
    os.environ['AZURE_CLIENT_ID'] = config.CLIENT_ID # visible in this process + all children
    os.environ['AZURE_CLIENT_SECRET'] = config.PASSWORD
    os.environ['AZURE_TENANT_ID'] = config.TENANT_ID

    credential = DefaultAzureCredential()

    key_client = KeyClient(vault_url=config.VAULT_URL, credential=credential)
    signClient = KeyVaultClient(KeyVaultAuthentication(auth_callback))
    w3 = Web3(HTTPProvider(config.ETHEREUM_ENDPOINT))

    test_txn = {'value': 1, 'chainId': None, 'gas': 70000, 'gasPrice': 1000000000, 'nonce': w3.eth.getTransactionCount('0x145dc3442412EdC113b01b63e14e85BA99926830'), 'to': destination}

    json_key = key_client.get_key("hsm-key").key
    pubkey = util.convert_json_key_to_public_key_bytes(json_key)
    address_signer = util.public_key_to_address(pubkey[1:])
    for i in range (test_txn['nonce'], test_txn['nonce']+repetitions):
        test_txn['nonce'] = i
        address_signer, signed_transaction = sign_keyvault(address_signer, signClient, config.VAULT_URL, config.KEY_NAME, config.KEY_VERSION, test_txn)
        
        # print("Signer", address_signer)
        # print("Unsigned transaction", test_txn)
        # print("Raw signed tx", signed_transaction.hex())
        tx_hash = w3.eth.sendRawTransaction(signed_transaction.hex())
        print("tx on etherscan: ", "https://rinkeby.etherscan.io/tx/" + tx_hash.hex())

    print("Sent whole " + str(repetitions) +  " transactions")
