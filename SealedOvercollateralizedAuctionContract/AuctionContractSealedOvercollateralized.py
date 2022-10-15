import base64

from algosdk.future import transaction
from algosdk import account, mnemonic
from algosdk.atomic_transaction_composer import *
from algosdk.v2client import algod
from pyteal import *
# from src.util import *
from util import *

from pyteal import *

ORDINARY_TYPE = 0
VICKREY_TYPE = 1

seller_key = Bytes("seller")
nft_id_key = Bytes("nft_id")
commit_end_key = Bytes("commit")
start_round_key = Bytes("start")
end_round_key = Bytes("end")
reserve_amount_key = Bytes("reserve_amount")
lead_bid_amount_key = Bytes("1st_amount")
lead_bid_account_key = Bytes("1st_account")
lead_bid_deposit_key = Bytes("1st_deposit")
second_highest_bid_amount_key = Bytes("2nd_amount")
contract_type_key = Bytes("contract_type")

commitment_local_key = Bytes("commitment")
deposit_local_key = Bytes("deposit")
#nonce_local_key = Bytes("nonce")

@Subroutine(TealType.none)
def closeNFTTo(assetID: Expr, account: Expr) -> Expr:
    asset_holding = AssetHolding.balance(
        Global.current_application_address(), assetID
    )
    return Seq(
        asset_holding,
        If(asset_holding.hasValue()).Then(
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.AssetTransfer,
                        TxnField.xfer_asset: assetID,
                        TxnField.asset_close_to: account,
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        ),
    )

@Subroutine(TealType.none)
def repayAmount(receiver: Expr, amount: Expr) -> Expr:
    return Seq(
        # Built inner Tx for repaying amount
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.amount: amount - Global.min_txn_fee(),
                TxnField.receiver: receiver,
            }
        ),
        InnerTxnBuilder.Submit(),
    )

@Subroutine(TealType.none)
def closeAccountTo(account: Expr) -> Expr:
    return If(Balance(Global.current_application_address()) != Int(0)).Then(
        Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.close_remainder_to: account,
                }
            ),
            InnerTxnBuilder.Submit(),
        )
    )

on_delete = Seq(
    If(Global.round() < App.globalGet(start_round_key)).Then(
        Seq(
            # the auction has not yet started, it's ok to delete
            Assert(
                Or(
                    # sender must either be the seller or the auction creator
                    Txn.sender() == App.globalGet(seller_key),
                    Txn.sender() == Global.creator_address(),
                    )
            ),
            # if the auction contract account has opted into the nft, close it out
            closeNFTTo(App.globalGet(nft_id_key), App.globalGet(seller_key)),
            # if the auction contract still has funds, send them all to the contract creator
            closeAccountTo(Global.creator_address()),
            Approve(),
        )
    ),
    If(App.globalGet(end_round_key) <= Global.round()).Then(
        Seq(
            # the auction has ended, pay out assets
            If(App.globalGet(lead_bid_account_key) != Global.zero_address())
            .Then(
                # If(
                #     App.globalGet(lead_bid_amount_key)
                #     >= App.globalGet(reserve_amount_key)
                # )
                # .Then(

                # The auction was successful:
                Seq(
                    # Send to the lead bid account the nft
                    closeNFTTo(
                        App.globalGet(nft_id_key),
                        App.globalGet(lead_bid_account_key),
                    ),
                    # Refund the lead bid account the overcollaterization depending on auction type
                    If(
                        App.globalGet(contract_type_key) == Int(VICKREY_TYPE)
                    ).Then(
                        # In case of Vickrey auction, return up to the second highest bid
                        # Check if the return is above the min transaction fee not to lock funds because nothing can be
                        # returned
                        If(
                            App.globalGet(lead_bid_deposit_key) - App.globalGet(second_highest_bid_amount_key) >=
                            Global.min_txn_fee()
                        ).Then(
                            repayAmount(
                                App.globalGet(lead_bid_account_key),
                                App.globalGet(lead_bid_deposit_key) - App.globalGet(second_highest_bid_amount_key),
                            ),
                        )
                    )
                    .Else(
                        # In case of ordinary auction, repay up to the highest bid
                        # Check if the return is above the min transaction fee not to lock funds because nothing can be
                        # returned
                        If(
                            App.globalGet(lead_bid_deposit_key) - App.globalGet(lead_bid_amount_key) >=
                            Global.min_txn_fee()
                        ).Then(
                            repayAmount(
                                App.globalGet(lead_bid_account_key),
                                App.globalGet(lead_bid_deposit_key) - App.globalGet(lead_bid_amount_key),
                            ),
                        )
                    ),
                    # Payout seller - depending on auction type
                    If(
                        App.globalGet(contract_type_key) == Int(VICKREY_TYPE)
                    ).Then(
                        # In case of Vickrey auction, payout the the second highest bid
                        repayAmount(
                            App.globalGet(seller_key),
                            App.globalGet(second_highest_bid_amount_key),
                        ),
                    )
                    .Else(
                        # In case of ordinary auction type, payout the highest bid
                        repayAmount(
                            App.globalGet(seller_key),
                            App.globalGet(lead_bid_amount_key),
                        ),
                    ),
                )

                # )
                # .Else(
                #     Seq(
                #         # the auction was not successful because the reserve was not met: return
                #         # the nft to the seller and repay the lead bidder
                #         closeNFTTo(
                #             App.globalGet(nft_id_key), App.globalGet(seller_key)
                #         ),
                #         repayAmount(
                #             App.globalGet(lead_bid_account_key),
                #             App.globalGet(lead_bid_amount_key),
                #         ),
                #     )
                # )
            )
            .Else(
                # The auction was not successful because no valid bids were made
                closeNFTTo(App.globalGet(nft_id_key), App.globalGet(seller_key))
            ),
            # send remaining funds (i.e. all non-revealed bids) to the contract creator
            closeAccountTo(Global.creator_address()),
            Approve(),
            )
    ),
    Reject(),
)

on_clear_state = Seq(
    # Check if the unrevealed bid is the highest made
    If(
        App.localGet(Txn.sender(), deposit_local_key) > App.globalGet(lead_bid_amount_key)
    ).Then(
        Seq(
            # Repay the previous highest bid
            If(App.globalGet(lead_bid_account_key) != Global.zero_address()).Then(
                repayAmount(
                    App.globalGet(lead_bid_account_key),
                    App.globalGet(lead_bid_amount_key),
                ),
            ),
            # Set the previous highest bid as the 2nd highest
            App.globalPut(second_highest_bid_amount_key, App.globalGet(lead_bid_amount_key)),
            # Set the new highest bid and the leading account
            App.globalPut(lead_bid_amount_key, App.localGet(Txn.sender(), deposit_local_key)),
            App.globalPut(lead_bid_account_key, Txn.sender()),
            # Set the deposit belonging to the highest bid
            App.globalPut(lead_bid_deposit_key, App.localGet(Txn.sender(), deposit_local_key)),
        )
    )
    .Else(
        Seq(
            # Check if the bid is 2nd highest
            If(
                App.localGet(Txn.sender(), deposit_local_key) > App.globalGet(second_highest_bid_amount_key)
            ).Then(
                # Set the bid as 2nd highest
                App.globalPut(second_highest_bid_amount_key, App.localGet(Txn.sender(), deposit_local_key)),
            ),
            # Return the full bid
            repayAmount(
                Txn.sender(),
                App.localGet(Txn.sender(), deposit_local_key),
            )
        )
    ),
    # Approve clearing local state
    Approve(),
)

def getRouter():
    # Main router class
    router = Router(
        # Name of the contract
        "SealedOvercollateralizedAuctionContract",
        # What to do for each on-complete type when no arguments are passed (bare call)
        BareCallActions(
            # On create only, just approve
            # no_op=OnCompleteAction.create_only(Approve()),
            # Always let creator update/delete but only by the creator of this contract
            # update_application=OnCompleteAction.always(Reject()),
            delete_application=OnCompleteAction.call_only(on_delete),
            # Opting out of local state will result in committing full collateral as bid, thus is discouraged
            close_out=OnCompleteAction.call_only(Reject()),
            clear_state=OnCompleteAction.call_only(on_clear_state),
        ),
    )


    @router.method(no_op=CallConfig.CREATE)
    def create_app(seller: abi.Account, nftID: abi.Uint64, startRound: abi.Uint64, commitEnd: abi.Uint64,
                   endRound: abi.Uint64, reserve: abi.Uint64, auctionType: abi.Uint64, *, output: abi.String) -> Expr:

        return Seq(
            # assert intended size of ABI compound type
            Assert(Len(seller.address()) == Int(32)),
            App.globalPut(seller_key, seller.address()),
            App.globalPut(nft_id_key, nftID.get()),
            App.globalPut(start_round_key, startRound.get()),
            App.globalPut(commit_end_key, commitEnd.get()),
            App.globalPut(end_round_key, endRound.get()),
            App.globalPut(reserve_amount_key, reserve.get()),
            App.globalPut(contract_type_key, auctionType.get()),
            App.globalPut(lead_bid_account_key, Global.zero_address()),
            # Set highest and second highest bid amounts to reserve amount
            App.globalPut(lead_bid_amount_key, reserve.get()),
            App.globalPut(second_highest_bid_amount_key, reserve.get()),
            # Set initial deposit amount of highest bid to zero
            App.globalPut(lead_bid_deposit_key, Int(0)),
            # Check if rounds are correctly set
            Assert(
                And(
                    Global.round() < startRound.get(),
                    startRound.get() < commitEnd.get(),
                    commitEnd.get() < endRound.get(),
                    )
            ),
            # Check if auction type is correctly set
            Assert(
                Or(
                    auctionType.get() == Int(ORDINARY_TYPE),
                    auctionType.get() == Int(VICKREY_TYPE),
                )
            ),
            output.set(seller.address())
        )

    @router.method(no_op=CallConfig.CALL)
    def on_setup():
        return Seq(
            # Check if auction hasn't yet started
            Assert(Global.round() < App.globalGet(start_round_key)),
            # opt into NFT asset -- because you can't opt in if you're already opted in, this is what
            # we'll use to make sure the contract has been set up
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.xfer_asset: App.globalGet(nft_id_key),
                    TxnField.asset_receiver: Global.current_application_address(),
                }
            ),
            InnerTxnBuilder.Submit(),
            Approve()
        )

    @router.method(opt_in=CallConfig.CALL)
    def on_commit(commitment: abi.DynamicBytes):
        on_commit_txn_index = Txn.group_index() - Int(1)
        on_bid_nft_holding = AssetHolding.balance(
            Global.current_application_address(), App.globalGet(nft_id_key)
        )

        return Seq(
            # assert intended size of ABI compound type for commitment
            Assert(Len(commitment.get()) == Int(32)),
            on_bid_nft_holding,
            Assert(And(
                # the auction has been set up
                on_bid_nft_holding.hasValue(),
                on_bid_nft_holding.value() > Int(0),
                # the auction is in the commit phase
                Global.round() >= App.globalGet(start_round_key),
                Global.round() < App.globalGet(commit_end_key),
                # Check if app call is accompanied by a payment transaction in the same group for collateral deposit
                Gtxn[on_commit_txn_index].type_enum() == TxnType.Payment,
                Gtxn[on_commit_txn_index].sender() == Txn.sender(),
                Gtxn[on_commit_txn_index].receiver() == Global.current_application_address(),
            )),
            App.localPut(Gtxn[on_commit_txn_index].sender(), commitment_local_key, commitment.get()),
            App.localPut(Gtxn[on_commit_txn_index].sender(), deposit_local_key, Gtxn[on_commit_txn_index].amount())
        )

    @router.method(no_op=CallConfig.CALL)
    def on_bid(nonce: abi.Uint64, amount: abi.Uint64):
        on_bid_nft_holding = AssetHolding.balance(
            Global.current_application_address(), App.globalGet(nft_id_key)
        )
        # App.localPut(Txn.sender(), nonce_local_key, nonce.get())
        Log(Sha256(Concat(Itob(amount.get()), Itob(nonce.get())))),
        return Seq(
            on_bid_nft_holding,
            Assert(
                And(
                    # the auction has been set up
                    on_bid_nft_holding.hasValue(),
                    on_bid_nft_holding.value() > Int(0),
                    # the auction is in the bidding/reveal phase
                    App.globalGet(commit_end_key) <= Global.round(),
                    Global.round() < App.globalGet(end_round_key),
                    # need Concat(byte1,byte2) to check multiple bytes
                    Sha256(Concat(
                        Itob(amount.get()),
                        Itob(nonce.get()))) ==
                        App.localGet(Txn.sender(), commitment_local_key),
                    )
            ),
            Log(Sha256(Concat(Itob(amount.get()), Itob(nonce.get())))),
            # Check if the bid is valid, i.e. larger or equal to deposited collateral
            If(
                amount.get() <= App.localGet(Txn.sender(), deposit_local_key),
            ).Then(
                # Check if the bid is the highest made
                If(
                    amount.get() > App.globalGet(lead_bid_amount_key)
                ).Then(
                    Seq(
                        # Repay the previous highest bid
                        If(App.globalGet(lead_bid_account_key) != Global.zero_address()).Then(
                            repayAmount(
                                App.globalGet(lead_bid_account_key),
                                App.globalGet(lead_bid_amount_key),
                            ),
                        ),
                        # Set the previous highest bid as the 2nd highest
                        App.globalPut(second_highest_bid_amount_key, App.globalGet(lead_bid_amount_key)),
                        # Set the new highest bid and the leading account
                        App.globalPut(lead_bid_amount_key, amount.get()),
                        App.globalPut(lead_bid_account_key, Txn.sender()),
                        # Set the deposit belonging to the highest bid
                        App.globalPut(lead_bid_deposit_key, App.localGet(Txn.sender(), deposit_local_key)),
                    )
                )
                .Else(
                    Seq(
                        # Check if the bid is 2nd highest
                        If(
                            amount.get() > App.globalGet(second_highest_bid_amount_key)
                        ).Then(
                            # Set the bid as 2nd highest
                            App.globalPut(second_highest_bid_amount_key, amount.get()),
                        ),
                        # Return the full bid
                        repayAmount(
                            Txn.sender(),
                            App.localGet(Txn.sender(), deposit_local_key),
                        ),
                    )
                )
            )
            .Else(
                # Return the full bid because it's invalid, i.e. it wasn't fully (over-)collateralized
                repayAmount(
                    Txn.sender(),
                    App.localGet(Txn.sender(), deposit_local_key),
                )
            ),
            # Delete local deposit
            App.localDel(Txn.sender(), deposit_local_key),
            Approve(),
        )

    return router