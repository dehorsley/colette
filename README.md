# Colette: Coffee Roulette — pair with a random person for coffee

## Installaiton

Requires Python 3.9 or later installed.

Open a command line and run:

    pip install colette

## Usage

Create a file called people.csv with at least columns 'name', 'organisation',
'email', and 'active'.

Each participating (or previously participating) player should be listed in
each row. The active column should contain 'true' if a player is going to
participate in new rounds.

Run, from a command line in the directory of your previously created
'people.csv':

    colette new

> Note: you may need to add the path pip installed colette too to your PATH
> enviroment variable.
>
> Alternativly you can run colette as
>
>     python -m colette

This will generate a new `round*.csv`, with pairs chosen to minimize the number
of people paired together in the same organisation, and those previously
paired. Players are assigned a role in each round, either "organiser" or
"(coffee) buyer". The method attempts to choose pairs that allow people to swap
roles each round.

If you want to mark certain pairs as desired or undesired, create an
"overrides.csv" file in the data directory, listing on each row the name of the two
players and an integer "cost" of adding this pair to the round. This will be
added to the cost of pairing if the players have previously been pair or are in
the same organisation. To prefer a pair, add a negative cost.
