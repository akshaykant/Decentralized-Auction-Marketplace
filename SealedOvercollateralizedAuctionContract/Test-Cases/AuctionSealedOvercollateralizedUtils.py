from hashlib import sha256
from random import randrange, seed

# Set seed of random generator for nonce - for testing purposes only!
seed(42)

from SealedOvercollateralizedAuctionContract.AuctionContractSealedOvercollateralized import *
# from src.committingAuction.AuctionContract import *
from algosdk.atomic_transaction_composer import AtomicTransactionComposer
from algosdk.logic import get_application_address

def getWinner(
        client: algod.AlgodClient,
        app_id: int,
        bidders_sk: str,
        bidders_addr: str,
):
    global_state = read_global_state(client, app_id)

    winner_addr = encoding.encode_address(global_state["1st_account"])
    winner_sk = bidders_sk[bidders_addr.index(winner_addr)]
    return winner_sk, winner_addr

def claimWinner(
        client: algod.AlgodClient,
        app_id: int,
        winner_sk: str
) -> None:
    global_state = read_global_state(client, app_id)
    nft_id = global_state['nft_id']

    suggestedParams = client.suggested_params()

    atc = AtomicTransactionComposer()
    winner_addr = account.address_from_private_key(winner_sk)
    winner_signer = AccountTransactionSigner(winner_sk)

    with open("./com_auction_contract.json") as f:
        js = f.read()

    atc.add_method_call(app_id=app_id,
                        method=get_method('payWinner', js),
                        sender=winner_addr,
                        sp=suggestedParams,
                        signer=winner_signer,
                        foreign_assets=[nft_id],
                        )

    result = atc.execute(client, 10)
    for res in result.tx_ids:
        print("\tTx ID:" + res)

    global_state = read_global_state(client, app_id)
    winnerClaimed = global_state['winner_paid']
    print("\tWinner claimed: ", winnerClaimed)

def claimSeller(
        client: algod.AlgodClient,
        app_id: int,
        seller_sk: str
) -> None:
    global_state = read_global_state(client, app_id)
    nft_id = global_state['nft_id']

    suggestedParams = client.suggested_params()

    atc = AtomicTransactionComposer()
    seller_addr = account.address_from_private_key(seller_sk)
    seller_signer = AccountTransactionSigner(seller_sk)

    with open("./com_auction_contract.json") as f:
        js = f.read()

    atc.add_method_call(app_id=app_id,
                        method=get_method('paySeller', js),
                        sender=seller_addr,
                        sp=suggestedParams,
                        signer=seller_signer,
                        foreign_assets=[nft_id],
                        )

    result = atc.execute(client, 10)
    for res in result.tx_ids:
        print("\tTx ID:" + res)

    global_state = read_global_state(client, app_id)
    sellerClaimed = global_state['seller_paid']
    print("\tSeller claimed: ", sellerClaimed)

def closeAuction(
        client: algod.AlgodClient,
        app_id: int,
        closer: str,
):
    app_addr = client.application_info(app_id).get('params').get('creator')

    global_state = read_global_state(client, app_id)

    nft_id = global_state['nft_id']

    accounts: List[str] = [encoding.encode_address(global_state["seller"])]

    if any(global_state["1st_account"]):
        # if "1st_account" is not the zero address
        accounts.append(encoding.encode_address(global_state["1st_account"]))

    # Not sure why this is needed
    accounts.append(app_addr)

    deleteTxn = transaction.ApplicationDeleteTxn(
        sender=account.address_from_private_key(closer),
        index=app_id,
        accounts=accounts,
        foreign_assets=[nft_id],
        sp=client.suggested_params(),
    )
    signedDeleteTxn = deleteTxn.sign(closer)

    client.send_transaction(signedDeleteTxn)
    transaction.wait_for_confirmation(client, signedDeleteTxn.get_txid())
    print("\t Tx ID:" + signedDeleteTxn.get_txid())

def placeBid(
        client: algod.AlgodClient,
        app_id: int,
        bidder_sk: str,
        bid_amount: int,
        nonce: int
) -> None:

    suggestedParams = client.suggested_params()
    global_state = read_global_state(client, app_id)
    nft_id = global_state['nft_id']

    atc = AtomicTransactionComposer()
    bidder_addr = account.address_from_private_key(bidder_sk)
    bidder_signer = AccountTransactionSigner(bidder_sk)

    with open("./com_auction_contract.json") as f:
        js = f.read()
    nonceHex = nonce#.to_bytes(8, 'big')
    app_args = [
        nonceHex,
        bid_amount
    ]

    atc.add_method_call(app_id=app_id,
                        method=get_method('on_bid', js),
                        sender=bidder_addr,
                        sp=suggestedParams,
                        signer=bidder_signer,
                        method_args=app_args,
                        foreign_assets=[nft_id],
                        )

    result = atc.execute(client, 10)
    for res in result.tx_ids:
        print("\tTx ID:" + res)

    print("\tGlobal state:", read_global_state(client, app_id))
    print("\tLocal state:", read_local_state(client, bidder_addr, app_id))


def commitAuctionApp(
        client: algod.AlgodClient,
        app_id: int,
        bidder_sk: str,
        value: int,
        nonce: int,
        deposit: int
):
    app_addr = get_application_address(app_id)
    global_state = read_global_state(client, app_id)
    nft_id = global_state['nft_id']
    suggestedParams = client.suggested_params()

    atc = AtomicTransactionComposer()
    bidder_addr = account.address_from_private_key(bidder_sk)
    bidder_signer = AccountTransactionSigner(bidder_sk)

    ptxn = transaction.PaymentTxn(bidder_addr, suggestedParams, app_addr, deposit)
    tws = TransactionWithSigner(ptxn, bidder_signer)
    atc.add_transaction(tws)

    with open("./com_auction_contract.json") as f:
        js = f.read()

    commitment = bytes(bytearray.fromhex(
        sha256(value.to_bytes(8, 'big')+nonce.to_bytes(8, 'big')).hexdigest()))
    app_args = [
        commitment
    ]
    print("\tCommitment (hex): " + commitment.hex())

    atc.add_method_call(
        app_id=app_id,
        method=get_method("on_commit", js),
        sender=account.address_from_private_key(bidder_sk),
        sp=suggestedParams,
        signer=bidder_signer,
        method_args=app_args,
        on_complete=transaction.OnComplete.OptInOC,
        foreign_assets=[nft_id]
    )

    result = atc.execute(client, 10)
    for res in result.tx_ids:
        print("\tTx ID:" + res)
    print("\tLocal state:", read_local_state(client, bidder_addr, app_id))



def setupAuctionApp(
        client: algod.AlgodClient,
        app_id: int,
        funder_sk: str,
        nft_holder_sk: str,
        nft_id: int,
):
    app_addr = get_application_address(app_id)

    suggestedParams = client.suggested_params()

    fundingAmount = (
        # min account balance
        100_000
        # additional min balance to opt into NFT
        + 100_000
        # 3 * min txn fee
        + 3 * 1_000
    )

    atc = AtomicTransactionComposer()
    funder_addr = account.address_from_private_key(funder_sk)
    nft_holder_addr = account.address_from_private_key(nft_holder_sk)
    signer_funder = AccountTransactionSigner(funder_sk)
    signer_nft_holder = AccountTransactionSigner(nft_holder_sk)

    ptxn = transaction.PaymentTxn(funder_addr, suggestedParams, app_addr, fundingAmount)
    tws = TransactionWithSigner(ptxn, signer_funder)
    atc.add_transaction(tws)

    with open("./com_auction_contract.json") as f:
        js = f.read()
    atc.add_method_call(app_id=app_id, method=get_method('on_setup', js), sender=funder_addr,
                        sp=suggestedParams, signer=signer_funder, foreign_assets=[nft_id])

    atxn = transaction.AssetTransferTxn(nft_holder_addr, suggestedParams, app_addr, 1, nft_id)
    tws = TransactionWithSigner(atxn, signer_nft_holder)
    atc.add_transaction(tws)

    result = atc.execute(client, 10)
    for res in result.tx_ids:
        print("\tTx ID:" + res)



def createAuctionApp(
        algod_client: algod.AlgodClient,
        senderSK: str,
        seller: str,
        nftID: int,
        startRound: int,
        commitRound: int,
        endRound: int,
        reserve: int,
        auction_type: int,
        serviceFee: int,
):
    # declare application state storage (immutable)
    local_ints = 1
    local_bytes = 1
    global_ints = 12
    global_bytes = 2
    global_schema = transaction.StateSchema(global_ints, global_bytes)
    local_schema = transaction.StateSchema(local_ints, local_bytes)

    # Compile the program
    router = getRouter()
    approval_program, clear_program, contract = router.compile_program(version=6,
                                                                       optimize=OptimizeOptions(scratch_slots=True))

    with open("./com_auction_approval.teal", "w") as f:
        f.write(approval_program)

    with open("./com_auction_clear.teal", "w") as f:
        f.write(clear_program)

    with open("./com_auction_contract.json", "w") as f:
        import json

        f.write(json.dumps(contract.dictify()))

    # compile program to binary
    approval_program_compiled = compile_program(algod_client, approval_program)

    # compile program to binary
    clear_state_program_compiled = compile_program(algod_client, clear_program)

    app_args = [
        seller,
        nftID,
        startRound,
        commitRound,
        endRound,
        reserve,
        auction_type,
        serviceFee
    ]

    atc = AtomicTransactionComposer()
    signer = AccountTransactionSigner(senderSK)
    sp = algod_client.suggested_params()

    with open("./com_auction_contract.json") as f:
        js = f.read()

    # Simple call to the `create_app` method, method_args can be any type but _must_
    # match those in the method signature of the contract
    atc.add_method_call(
        app_id=0,
        method=get_method("create_app", js),
        sender=account.address_from_private_key(senderSK),
        sp=sp,
        signer=signer,
        approval_program=approval_program_compiled,
        clear_program=clear_state_program_compiled,
        local_schema=local_schema,
        global_schema=global_schema,
        method_args=app_args
    )

    result = atc.execute(algod_client, 10)
    app_id = transaction.wait_for_confirmation(algod_client, result.tx_ids[0])['application-index']

    for res in result.tx_ids:
        print("\tTx ID: " + res)
    print("\tGlobal state:", read_global_state(algod_client, app_id))

    assert app_id is not None and app_id > 0
    return app_id, contract
