# Notes on how to work with this project


## Introduction
The following notes should help the user understand how to test the collection of smart contract

## Libraries
By doing

```bash
pip3 install -r requirements.txt
```

you will have all the required libraries to use the code provided in the smart contract

## Mnemonic 
To deploy the smart contract it is necessary to have a private key to sign the transaction. As far as the contract goes, the private key is derived from a mnemonic phrase. 

Our smart contract reads the mnemonic from a file called `mnemonic.txt` (which is in the `.gitignore` file by default, so that it is not uploaded). Assuming you are using the standard `goal` command, getting the mnemonic for address `ALKJ6F2OD7COCWD2ROP5QKTMXRCJRS6U5QA34V2TVPNNU4PWIW4RSSUUIE` can be done doing:

```
$ goal account export -a ALKJ6F2OD7COCWD2ROP5QKTMXRCJRS6U5QA34V2TVPNNU4PWIW4RSSUUIE

Exported key for account ALKJ6F2OD7COCWD2ROP5QKTMXRCJRS6U5QA34V2TVPNNU4PWIW4RSSUUIE: "funny another because afraid range artwork table switch drive life avocado world present thought absorb dinner neutral melt gallery siren punch puzzle survey ability ivory"
``` 

so that the mnemonic phrase is `funny another .... ivory` (no `"`) and it should be put in the `mnemonic.txt` file this way. 

If you are using [the Algorand sandbox](https://github.com/algorand/sandbox) the command is similar:

```
$ ./sandbox goal account export -a ALKJ6F2OD7COCWD2ROP5QKTMXRCJRS6U5QA34V2TVPNNU4PWIW4RSSUUIE
```

By doing things this way you don't have to change any hardcoded variable. The mnemonic is managed by the python script this way:

```python
# user declared account mnemonics
with open('mnemonic.txt','r') as f:
    creator_mnemonic = f.read()
```

## Contracts

There are three contracts:
- Normal Auction contract in the directory [AuctionContract](./AuctionContract)
- Sealed Auction contract in the directory [SealedAuctionContract](./SealedAuctionContract)
- Sealed Overcollateralized Auction contract in the directory [SealedOvercollateralizedAuction](./SealedOvercollateralizedAuction)

The Normal and Sealed contracts have a python script ([AuctionContract/AuctionMain.py](AuctionContract/AuctionMain.py) and [SealedAuctionContract/AuctionMainSealed.py](SealedAuctionContract/AuctionMainSealed.py) respectively) which deploys the contract, bids (or commits and bids in the sealed one) and sends the NFT to the winner. 

The Sealed Overcollateralized Auction has two different test cases that can be found in the [SealedOvercollateralizedAuctionContract/Test-Cases](SealedOvercollateralizedAuctionContract/Test-Cases) directory.