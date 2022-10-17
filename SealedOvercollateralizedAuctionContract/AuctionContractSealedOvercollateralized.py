import base64

from algosdk.future import transaction
from algosdk import account, mnemonic
from algosdk.atomic_transaction_composer import *
from algosdk.v2client import algod
from pyteal import *
# from src.util import *
from util import *

from pyteal import *

HAS_NOT_BEEN_PAID = 0
HAS_BEEN_PAID = 1

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
second_highest_bid_amount_key = Bytes("2nd_amount")
auction_type_key = Bytes("auction_type")
service_fee_key = Bytes("service_fee")
seller_has_been_paid_key = Bytes("seller_paid")
winner_has_been_paid_key = Bytes("winner_paid")

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
    # If the auction has not yet started, it's ok to delete it
    If(Global.round() < App.globalGet(start_round_key)).Then(
        Seq(
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
    # If all payouts have been made, it's ok to delete it
    If(
        And(
            App.globalGet(seller_has_been_paid_key) == Int(HAS_BEEN_PAID),
            App.globalGet(winner_has_been_paid_key) == Int(HAS_BEEN_PAID),
        )
    ).Then(
        Seq(
            # send remaining funds (i.e. all non-revealed bids) to the contract creator
            closeAccountTo(Global.creator_address()),
            Approve(),
        ),
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
                   endRound: abi.Uint64, reserve: abi.Uint64, auctionType: abi.Uint64, serviceFee: abi.Uint64, *,
                   output: abi.String) -> Expr:

        return Seq(
            # assert intended size of ABI compound type
            Assert(Len(seller.address()) == Int(32)),
            App.globalPut(seller_key, seller.address()),
            App.globalPut(nft_id_key, nftID.get()),
            App.globalPut(start_round_key, startRound.get()),
            App.globalPut(commit_end_key, commitEnd.get()),
            App.globalPut(end_round_key, endRound.get()),
            App.globalPut(reserve_amount_key, reserve.get()),
            App.globalPut(auction_type_key, auctionType.get()),
            App.globalPut(service_fee_key, serviceFee.get()),
            App.globalPut(lead_bid_account_key, Global.zero_address()),
            # Set highest and second highest bid amounts to reserve amount
            App.globalPut(lead_bid_amount_key, reserve.get()),
            App.globalPut(second_highest_bid_amount_key, reserve.get()),
            # Mark that neither seller nor winner have been paid
            App.globalPut(seller_has_been_paid_key, Int(HAS_NOT_BEEN_PAID)),
            App.globalPut(winner_has_been_paid_key, Int(HAS_NOT_BEEN_PAID)),
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
                        # Return the overcollaterization of the new lead bid
                        If(
                            App.localGet(Txn.sender(), deposit_local_key) - App.globalGet(lead_bid_amount_key) >=
                            Global.min_txn_fee()
                        ).Then(
                            repayAmount(
                                Txn.sender(),
                                App.localGet(Txn.sender(), deposit_local_key) - App.globalGet(lead_bid_amount_key),
                            ),
                        ),
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

    @router.method(no_op=CallConfig.CALL)
    def paySeller():
        return Seq(
            Assert(
                And(
                    # Check if the auction has ended
                    App.globalGet(end_round_key) <= Global.round(),
                    # Check if the sender is the seller - i.e. wants the payout
                    Txn.sender() == App.globalGet(seller_key),
                    # Check if the seller hasn't been paid yet
                    App.globalGet(seller_has_been_paid_key) == Int(HAS_NOT_BEEN_PAID),
                )
            ),
            # Check if auction received any valid bids
            If(
                App.globalGet(lead_bid_account_key) != Global.zero_address()
            ).Then(
                # Auction was successful => pay out the seller depending on auction type
                If(
                    App.globalGet(auction_type_key) == Int(VICKREY_TYPE)
                ).Then(
                    # In case of Vickrey auction, payout the the second highest bid
                    repayAmount(
                        App.globalGet(seller_key),
                        # Charge service fees through equation: X-fee*(X/100) to prevent overflows
                        Minus(
                            App.globalGet(second_highest_bid_amount_key),
                            Mul(
                                App.globalGet(service_fee_key),
                                Div(
                                    App.globalGet(second_highest_bid_amount_key),
                                    Int(100)
                                )
                            )
                        ),
                    ),
                )
                .Else(
                    # In case of ordinary auction type, payout the highest bid
                    repayAmount(
                        App.globalGet(seller_key),
                        # Charge service fees through equation: X-fee*(X/100) to prevent overflows
                        Minus(
                            App.globalGet(lead_bid_amount_key),
                            Mul(
                                App.globalGet(service_fee_key),
                                Div(
                                    App.globalGet(lead_bid_amount_key),
                                    Int(100)
                                )
                            )
                        ),
                    )
                )
            )
            .Else(
                # Auction was not successful because no valid bids were received => return the NFT to the seller
                # Note: if seller has opted-out of the NFT, the Tx will fail and NFT will remain in the smart contract
                # until it has been retrieved.
                closeNFTTo(
                    App.globalGet(nft_id_key),
                    App.globalGet(seller_key)
                ),
            ),
            # Mark that the seller has been paid
            App.globalPut(seller_has_been_paid_key, Int(HAS_BEEN_PAID)),
            Approve(),
        )

    @router.method(no_op=CallConfig.CALL)
    def payWinner():
        return Seq(
            Assert(
                And(
                    # Check if the auction has ended
                    App.globalGet(end_round_key) <= Global.round(),
                    # Check if the sender is the winner - i.e. wants the payout
                    Txn.sender() == App.globalGet(lead_bid_account_key),
                    # Check if the winner hasn't been paid yet
                    App.globalGet(winner_has_been_paid_key) == Int(HAS_NOT_BEEN_PAID),
                )
            ),
            # Send the NFT to the winner
            # Note: if winner isn't opted-in the NFT, the Tx will fail and NFT will remain in the smart contract
            # until it has been claimed.
            closeNFTTo(
                App.globalGet(nft_id_key),
                App.globalGet(lead_bid_account_key)
            ),
            # In case of Vickrey auction, return to the winner up to the second highest bid
            If(
                App.globalGet(auction_type_key) == Int(VICKREY_TYPE)
            ).Then(

                # Check if the return is above the min transaction fee not to lock funds because nothing can be
                # returned in this case
                If(
                    App.globalGet(lead_bid_amount_key) - App.globalGet(second_highest_bid_amount_key) >=
                    Global.min_txn_fee()
                ).Then(
                    repayAmount(
                        App.globalGet(lead_bid_account_key),
                        App.globalGet(lead_bid_amount_key) - App.globalGet(second_highest_bid_amount_key),
                    ),
                )
            ),
            # Mark that the winner has been paid
            App.globalPut(winner_has_been_paid_key, Int(HAS_BEEN_PAID)),
            Approve(),
        )

    return router
