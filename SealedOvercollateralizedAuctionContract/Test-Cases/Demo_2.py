# Description of demo 2:
#  This script demonstrates a case of a Vickrey style auction with overcollateralization.
#  Three bidders compete for a NFT. All create valid bids - i.e. above the asking price and overcollateralized.
#  The bid amounts of the first and second bidder are identical, just different collaterals are deposited.
#  The first bidder does not deposit any additional collateral above the bid amount.
#  The second one bidder deposits extra collateral to obfuscate their bid amount.
#  The third bidder deposits even more collateral than the second one but their bid is smaller than the other two.
#  All bidders reveal their bids during the reveal phase.
#  The one of the two bidders with equal bid amounts that first reveals the bid wins the NFT.
#  Other two bidders get their collateral refunded.
#  The winner opts in the NFT and claims it.
#  The winner does not get anything refunded because the second bid is equal to their deposited collateral.
#  The seller claims the payment. A service fee is deducted from that amount (which remains in the contract account).
#  The contract is deleted and the remaining funds (including the service fee) send to the contract creator.

# -----------------           Imports          -----------------
from random import randrange, seed
from AuctionSealedOvercollateralizedUtils import *

# -----------------   User defined variables   -----------------
# Main account mnemonic.
# The account funds all other addresses that interact with the smart contract. Should have at least 10 Algo.
with open('../../mnemonic.txt', 'r') as f:
    creator_mnemonic = f.read()

# Number of bidder accounts
NUM_BID_ACCS = 3

# Algod connection parameters. Node must have EnableDeveloperAPI set to true in its config
algod_address = "https://node.testnet.algoexplorerapi.io"  # "http://localhost:4001"  # "https://node.testnet.algoexplorerapi.io"
algod_token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Auction type. Possible options:
# - ORDINARY_TYPE = sealed-bid first-price auction
# - VICKREY_TYPE = sealed-bid second-price auction
AUCTION_TYPE = VICKREY_TYPE

# Amount to fund bidder and seller accounts with
AMT = 1_000_000

# Minimal asking price for the NFT (in microAlgo)
RESERVE = 100_000

# Bids of account (in microAlgo)
BID_AMOUNTS = [200_000, 200_000, 150_000]

# Deposits, i.e. collateralization of bids, for each account (in microAlgo)
DEPOSITS = [200_000, 290_000, 410_000]

# Fee taken by the contract creator as percentage of the winning bid
SERVICE_FEE = 2

# Set seed of random generator - for testing purposes only!
seed(42)
# Nonces for obfuscation of bids
NONCES = [randrange(0, 600) for i in range(NUM_BID_ACCS)]

# Number of instances of NFT minted
NFT_AMOUNT = 1

# Assumed block production time (in seconds)
BLOCK_TIME = 3.9

# Starting auction time - defined as seconds from time when all relevant accounts have been set.
# The seconds are rounded to closest block number.
TIME_TO_AUCTION = 40  # 20  # 40
# Duration of the commit phase of the auction (in seconds).
# The seconds are rounded to closest block number.
COMMIT_DURATION = 45  # 25  # 45
# Duration of the bid reveal (i.e. opening) phase of the auction (in seconds).
# The seconds are rounded to closest block number.
REVEAL_DURATION = 41  # 21  # 41


# ---------------------------------------------------------------

def main():

    # Initialize an algodClient
    algod_client = algod.AlgodClient(algod_token, algod_address)

    print("Relevant addresses:")
    creator_private_key = get_private_key_from_mnemonic(creator_mnemonic)
    creator_address = account.address_from_private_key(creator_private_key)
    print("\tContract creator address: ", creator_address)

    # Create a seller account
    seller_sk = account.generate_account()[0]
    seller = account.address_from_private_key(seller_sk)
    print("\tNTF seller address: ", seller)

    # Create NUM_BID_ACCS bidder accounts
    bidders_sk = [account.generate_account()[0] for i in range(NUM_BID_ACCS)]
    bidders = [account.address_from_private_key(i) for i in bidders_sk]
    for i, b in enumerate(bidders):
        print("\tBidder {} address: {}".format(i, b))

    # Fund seller and bidder accounts
    print(f"Creator address funding other relevant accounts with {AMT} microAlgo...")
    fundAccount(algod_client, creator_address, seller, creator_private_key, AMT)
    for b in bidders:
        fundAccount(algod_client, creator_address, b, creator_private_key, AMT)

    print("\n--------------------------------------------")
    # Seller creates an NFT
    nftID = createDummyAsset(algod_client, NFT_AMOUNT, seller, seller_sk)
    print("Seller created an NFT with ID: ", nftID)

    print("\n--------------------------------------------")
    # Create the auction
    currentRound = algod_client.status().get('last-round')
    startRound = currentRound + round(TIME_TO_AUCTION / BLOCK_TIME)
    commitDurationRounds = round(COMMIT_DURATION / BLOCK_TIME)
    commitEndRound = startRound + commitDurationRounds
    revealDurationRounds = round(REVEAL_DURATION / BLOCK_TIME)
    endRound = commitEndRound + revealDurationRounds

    print("\nCreating sealed-bid auction for NFT during round: ", currentRound+1)
    if AUCTION_TYPE == VICKREY_TYPE:
        print("\tAuction type: Vickrey = sealed-bid second-price auction")
    elif AUCTION_TYPE == ORDINARY_TYPE:
        print("\tAuction type: ordinary = sealed-bid first-price auction")
    else:
        raise Exception("Unknown auction type")

    print("\tCommit period lasting {} rounds\n\tRevealing period lasting {} rounds".format(
        commitDurationRounds, revealDurationRounds))

    app_id, contract = createAuctionApp(algod_client, creator_private_key,
                                        seller, nftID, startRound, commitEndRound,
                                        endRound, RESERVE, AUCTION_TYPE, SERVICE_FEE)

    print("Created contract with AppID: ", app_id)

    print("\n--------------------------------------------")
    print("Setting the auction application ...")
    setupAuctionApp(algod_client, app_id, creator_private_key, seller_sk, nftID)
    # Wait for the auction to start
    print("Waiting for the auction to start.")
    waitUntilRound(algod_client, startRound)
    print("--------------------------------------------")
    print("Committing bids to the auction ...")
    for i, bsk in enumerate(bidders_sk):
        commitAuctionApp(algod_client, app_id, bsk, BID_AMOUNTS[i], NONCES[i], DEPOSITS[i])
    # Wait for the commit period to end
    waitUntilRound(algod_client, commitEndRound)
    print("Commit phase ended.")
    print("--------------------------------------------")
    print("Revealing the auction bids ...")
    for i, bsk in enumerate(bidders_sk):
        placeBid(algod_client, app_id, bsk, BID_AMOUNTS[i], NONCES[i])
    # Wait for the auction to end
    waitUntilRound(algod_client, endRound)
    print("Auction ended.")
    print("--------------------------------------------")
    print("Winner opting in the NFT ...")
    winner_sk, winner_addr = getWinner(algod_client, app_id, bidders_sk, bidders)
    optInToAsset(algod_client, nftID, winner_sk)
    print("Winner opted in the NFT.")

    print("Winner claiming the NFT ...")
    claimWinner(algod_client, app_id, winner_sk)
    print("Winner claimed the NFT.")

    print("Seller claiming the payout ...")
    claimSeller(algod_client, app_id, seller_sk)
    print("Seller claimed the NFT.")

    # Wait for one round for easier inspection of app state with Sandbox
    currentRound = algod_client.status().get('last-round')
    waitUntilRound(algod_client, currentRound + 1)

    print("Closing the auction application ...")
    closeAuction(algod_client, app_id, creator_private_key)
    print("Application closed. Remaining funds returned to the contract creator.")

if __name__ == "__main__":
    main()
