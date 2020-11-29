# Colette: Coffee Roulette — pair with a random person for coffee

WIP

## Usage
Create a file in subdirectory 'data' called people.csv with at least columns
'name', 'organisation',  and 'active'. 

Each participating (or previously participating) player should be listed in each row. The
active column should contain 'true' if a player is going to participate in new
rounds.

Run

    python colette.py

This will generate a new `round*.csv`, with pairs chosen to minimize the number
of people paired together in the same company, previously paired. Players are
assigned a role in each round, either "organiser" or "(coffee) buyer".
