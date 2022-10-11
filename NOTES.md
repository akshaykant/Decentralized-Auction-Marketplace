# Notes on how to work with this project


## Intro
The folling notes should help the user understand how to test the collection of smart contract

## Mnemonic 
to deploy the smart contract it is necessary to have a private key to sign the transaction. As far as the contract goes, the private key is derived from a mnemonic phrase. 

Our smart contract reads the mnemonic from a file called `mnemonic.txt` (which is in the `.gitignore` file by default, so that it is not uploaded). Assuming you are usign the standard `goal` command, getting the mnemonic fro address `ALKJ6F2OD7COCWD2ROP5QKTMXRCJRS6U5QA34V2TVPNNU4PWIW4RSSUUIE` can be done doing:

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