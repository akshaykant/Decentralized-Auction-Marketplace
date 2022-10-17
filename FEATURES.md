# Features Rationale

We added new features to the smart contracts. In the following we briefly explain the rationale behind our choices.

The features are:
- the introduction of a [service fee](#service-fee)
- the possibility for [overcollateralization](#overcollateralizaton)
- the possibility for [Vickrey auctions](#vickrey-auctions)



## Service fee
Operating a NFT manager has costs, both in terms of money (ALGO in this case) and opportunity. It is convinient for the manager to be rewarded for its services. For this reason we introduced the possibility for the manager to get fees. 

As per the implementation, the percentage of the fees is a parameter passed during the creation of the app. For this reason the creator may decide to receive no fees, perhaps as an entry offering for first time use of its services.

## Overcollateralization
Auctions can be public or private. The problem with public auctions is that users can tailor the bid to the previous bidds, effectively saving money in case of less crowded auctions. this is against the spirit of auctions were the bidder should bid truthfully, i.e. according to what the bidded intends to pay for the asset. So it may be  better to have private auctions.

To make a private auction on a permissionless and public blockchain, the best thing to do is using committed values that will be revealed after a certain time. The problem with this approach is that bidder do not invest any coins in the bidding process before the revealing, which means a malicious bidder `M` can make multiple commitment and reveal only the one which is most convenient for `M` (since at revealing-time the auction becomes essentially public). This is basically [DDoS attack on an auction](https://www.secureworld.io/industry-news/cyber-attack-rare-whisky-auction-stopped), which should be prevented.

One way to do that is by requiring bidders to overcollateralize their bid: A bidder `B` puts a collateral which must be *higher* than the amount `B` committed to. The collateral becomes effectively an upper bound of the amount `B` will eventually pay. This way rpivacy for `B` is achieved, while avoiding any kind of spam or malicious attack.

Of course, this has some disadvantages to, such as the opportunity cost for `B`: if more than the necessary amount of coin is locked, `B` may not participate in other auctions for example.

It is therefore a tradeoff between security for the creator and usability for the bidder, and therefore we provided both kind of contracts.

## Vickrey Auctions

We mentioned that in public auctions people can get away with paying *less* than their original intentions since they can see what other bidders are bidding. In private auctions the problem is reversed: people risk paying more than necessary since they can not see what other people are bidding. In other words, both kinds of auctions are not fair.

To mitigate the problem, in the Vickrey auction (a particular kind of sealed-bid, and therefore private, auction) bidderd commit to a value for the asset, but the winner pays the *amount of the second highest-bid*. In this case the bidders are encouraged to bid a littel bit more (better for the seller) while knowing that, if they win, they will pay a little bit less (better for the bidders). In other words, a win-win.

On the other hand, it could be argued that the Vickrey auction does not allow for price discovery, since the price eventually paid is inherently "false", since it does not represent what people are willing to pay. As in the [overcollateralization](#overcollateralization) case, this is a tradeoff and we let the creator of the auction choose by setting a variable:

```python
ORDINARY_TYPE = 0
VICKREY_TYPE = 1
```