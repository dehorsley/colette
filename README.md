# Colette: Coffee Roulette — pair with a random person for coffee

## Installation

First download Python - anaconda is a good place to start (https://www.anaconda.com/products/individual). Colette requires Python 3.9+.

*Colette* is found here: https://github.com/dehorsley/colette and is installed within the Python package system PyPi (similar to an **R** package.

To install the package in Python run the following code in the command line (this doesn't work in Jupyter - not sure why):

**pip install colette**

Once installed, make sure you have the correct files in your file path. To run a coffee roulette, you will need:

1) A .csv file named **people.csv** with the following headings: 'name', 'organisation', 'email', and 'active'. Active is binary (1=active, 0=inactive). Other columns are character, and can have any format. Each participating (or previously participating) player should be listed on an individual row.

2) A .csv file named **overrides.csv** with two columns, one with a name, and the second with a penalty factor (1000). The names in the first column will not be paired together. I haven't figured out how to not pair specific people if there are more than two of them...

3) Templates: **buyer.template**, **excluded.template**, **organiser.template**. These are used when auto-generating emails to participants. They could look something like this (this is the **buyer.template**):

*Hi {{buyer.name}},*
*This round of coffee roulette you've been paired with {{organiser.name}} from {{organiser.organisation}}.*
*They will contact you to arrange a venue and time, your only job this month is to buy the coffee!*

*Some things to talk about:*

*1. What your current role is*
*2. Where you've worked previously*
*3. Where you'd like to work in the future*
*4. The merits of 'Zoom-shirts'*

*Happy networking!*

*PS. Perhaps add {{organiser.email}} to your address book to make sure it doesn't get flagged as spam.*

**Note that these are not HTML so formatting can look a little strange. Double curly brackets - {{}} will contain email information that you have populated in the *people.csv* file.**

4) An **email.ini** file - this needs the following format:

[email]
from = Joe Bloggs <email.name@emailprovider.com>
subject = Coffee Roulette
server = 
port = 
ssl = 
username = email.name@emailprovider.com
password = thepasswordfortheaccount

**Once you have these files, you're ready to go**

# Running the roulette

Once you have the files, and have installed *colette*, it's probably a good idea to test the email functionality **before** doing an official round - the package automatically sends the emails out.

To generate a new round, run the following line: The active column should contain 'true' if a player is going to participate in new rounds.

Run, from a command line in the directory of your previously created 'people.csv':

**colette new**

This will generate a new round*.csv, with pairs chosen to minimize the number of people paired together in the same organisation, and those previously paired. Players are assigned a role in each round, either "organiser" or "(coffee) buyer". The method attempts to choose pairs that allow people to swap roles each round.

If you want to mark certain pairs as desired or undesired, create an "overrides.csv" file in the data directory, listing on each row the name of the two players and an integer "cost" of adding this pair to the round. This will be added to the cost of pairing if the players have previously been pair or are in the same organisation. To prefer a pair, add a negative cost.

If successful, the following message will appear:

**Generating Round 1!**

After you have generated a few rounds, some warning messages may appear such as:

*Bob Builder paired with Thomas Tank but players were the same role last round.*

You could re-run the round, and add higher penalising factors if someone keeps being the buyer for instance. I have not fully worked out how to do this yet.

# Emailing participants

Once happy with the round, you are ready to email people. Make sure the *.template* files, and the *email.ini* file is correctly populated. Then, in the command line, run:

**colette email**

If successful, the following message will appear:

**Emailing players of round 1!**

This step can take a minute or so. Once done, there's no extra message. But hopefully your roulette participants will have received an email with their coffee partner!

Happy rouletting. Any problems with code functionality, post them here: https://github.com/dehorsley/colette. 

Any questions on setting up or facilitating networking events, email: fisheries.network@gmail.com or contact https://github.com/gacphillips.

> Note: you may need to add the path pip installed colette too to your PATH
> enviroment variable.
>
> Alternative
ly you can run colette as
>
>     python -m colette
