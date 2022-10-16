# Algorand School Project Proposal

## Group G4: 
1. Uroš Hudomalj - https://github.com/uhudo
2. Fadi Barbara - https://gihub.com/disnocen
3. Akshay Kant - https://github.com/akshaykant

*Project Name: Decentralized Auction marketplace*

## Intro
This is a draft for the Algorand school proposal. The goal is to improve on the NFT auction smart contract (https://github.com/algorand-school/handson-contract) and build a decentralised auction marketplace where sellers can choose different auction mechanisms (like Sealed bid auction, Vickrey auction and Dutch auction) to list the NFT on auction.


## Roadmap
- [X] Sealed bid auction (Target Implementation)
- [X] Service fees (Target Implementation)
- [X] Overcollateralization (Target Implementation)
- [X] Improve seal bidding with nonce for better security (Target Implementation)
- [X] Vickrey auction (Future Goal)

- [ ] Marketplace (Stretch Goal)
- [ ] Dutch auction (Future)


## Decentralized Auction Marketplace Mechanics: 

- Auction Contract which will act as the parent/entry point to smart contracts.
- List Function: take the NFT along with arguments like reserve price and duration of the auction along with the choice of auction mechanism (sealed auction). This will deploy a unique contract along with all the parameters for that auction and transfer NFT into the custody of that `app_id`. Also, store the `app_id` in the global storage.
- Send Sealed Bid
hash(nonce, amount) - represent the sealed bid along with `app_id` of the auction. The auction marketplace can check the global storage if `app_id` exists and send the sealed bid. Auction with `app_id` will store the sealed bin in global storage and replace it if there was already sent.
- Send Opening Bid
Send `nonce`, the amount along with payment and `app_id`. Auction contract checks if openings could be received and accept payment transaction only if it reaches the reserve price. If the auction holds the previous highest bid and the recent one is higher, accept the new one and return funds to the previous higher bid.

## Economics of protocol
Fees from the seller to make the decentralized protocol running which included Service fees - 2% fees of winning bid


## Goal 

Auction Marketplace with global/local storage with 20 users, moving to Box storage (https://github.com/algorand/go-algorand/pull/4001) for scalability


## Open Questions

- For project initiation which features should we implement?

- How does global storage work? Who pays for the allocated space?
  Here is the open question - https://forum.algorand.org/t/global-storage-fees/7996

- Complexity of building an auction marketplace that supports multiple auction types?

- Current Algorand smart contract architecture has a limitation for global storage which will be resolved with the introduction of Box storage. So we could consider Box storage as an upgrade for a more involved and scalable application?
