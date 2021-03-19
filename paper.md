---
title: 'Collete: A networking program for coffee-pairings to build research connections'
tags:
  - Python
  - fisheries
  - networking
  - coffee-pairings
authors:
  - name: David E. Horsley 
    orcid: 0000-0002-5601-6496
    affiliation: 1
  - name: Genevieve A.C. Phillips^[Corresponding author]
    orcid: 0000-0002-2347-2321
    affiliation: "2,3"
affiliations:
 - name: Horsley Consulting
   index: 1
 - name: Institute of Marine and Antarctic Studies, University of Tasmania
   index: 2
 - name: Centre for Marine Socioecology, University of Tasmania
   index: 3
date: "2021-03"
bibliography: paper.bib

---

# Summary

Effective scientific collaboration is necessary to make efficient use of
limited funding to solve issues common across fisheries science. Instigating
and facilitating networking across multiple government and research
organisations, and disciplines is one way of improving the chances of new
collaborations forming. With a lack of in-person conferences and inter-group
workshops in 2020, there was an opportunity to find a new way to create links
between fisheries scientists in organisations based in Hobart. A common
obstruction within government departments and research organisations is access
to simple, free, open-access software to facilitate networking that does not
increase administrative burdens. The software randomly pairs people from
different organisations, for multiple rounds of networking, while taking into
account individuals leaving, joining, or re-joining the group. The software contains functionality
to automatically email participants based on pre-constructed templates.

# Statement of need

`Colette` is a Python package for facilitating networking. `Colette` allows
for random pairings of individuals from multiple organisations in a
population. Pairings are favoured between individuals of different
organisations, and recent pairings between individuals are penalised so that
individuals meet as many others within the population as possible before
re-pairings occur. Each run of the software produces one round of pairings.

The novel aspect of the program is that multiple rounds of unique pairings are possible and are generated
based on prior rounds. This allows for ease of tracking pairings,
and assurance that individuals are not being randomly assigned to the same
partner each round. Individuals can leave and re-join the population with no penalty,
and with the reduced likelihood of pairing with their last partner when they return.
The package allows for interfacing with an SMTP server to automate emails if
required or desired.

Python was chosen due to the author's familiarity with the language and the
number of high quality packages available for operations research and email
creation.

`Colette` is designed to be used by anyone wanting to facilitate
collaboration pairings. It is currently being used in Hobart to facilitate
coffee pairings between fisheries scientists at the University of Tasmania,
the Commonwealth Scientific and Industrial Research Organisation (CSIRO), the
Australian Antarctic Division (within the Commonwealth Department of
Agriculture, Water, and the Environment), and the Tasmanian State Department
for Primary Industry, Parks, Wildlife and the Environment (DPIPWE), and has
already facilitated collaborations between interdisciplinary scientists. The
software will also be used by the Institute of Marine and Antarctic Studies
(IMAS) postdoctoral researchers for speed-networking events.

# Method

The main idea behind `Colette` is to randomly pair people from different
organisations or groups to maximise networking opportunities. Therefore, the
main desired properties of the program's output are that:

1)  Pairings are favoured between people in different organisations (i.e. a
    person from the Australian Antarctic Division (AAD) will be paired with
    someone from any other organisation before being paired with someone from
    the AAD).

2)  Novel pairings are favoured over those that have already occurred in
    previous rounds. The implementation currently only considers the previous 10 rounds of pairings.

3)  Each person is given a role in the pair -
    coffee 'buyer' or venue 'organiser' (i.e. a 'buyer' in round 1 will be
    paired with a 'buyer' in the following round, so they become the
    'organiser'). This is done to prevent a stand-off where each participant is expecting
    the other to reach out and organise the meet-up. Pairs that allow the players to swap their
    role from their previous round are prefered.

4)  If no satisfactory pairing can be made for a player, the player is
    excluded from the round. For example if there are an odd number of players within the population, or
    the player has recently paired with all others available. In the current
    implementation, this is recorded by the player concerned being paired with themselves and output in a CSV file. This functionality allows the organiser to keep a record for future rounds that will prevent a player from being repeatedly
    excluded, and to differentiate from a when a player did not participate in the
    round voluntarily (i.e. they opted out).

To find pairs satisfying the above requirements efficiently, we formulate the
problem as a linear integer program and use the advanced techniques
available to solve such optimisation problems. In the current implementation
we use the COIN-OR CBC solver [@coin-or-cbc], via the Python MIP package
[@python-mip], to find solutions to the problem. The CBC solver uses the
Branch-and-Cut method, an efficient method specialised for linear integer
programs such as the one we formulate here.

To state the problem as an integer program, we begin by considering finding 
pairs in the $R$th round, with N "players". We let

$$
p_{ij} \in \{0,1\}, \quad 1\le i \le N,\ i \le j \le N,
$$

denote that player $i$ and $j$ are to be paired in the current round.
Here we have used variables with the same index, $p_{ii}$, to denote that the
player $i$ has been excluded from the round. This allows us to track player exclusion
which is useful when we formulate the objective for the problem.

Our one constraint on the decision variables $p_{ij}$ come from the requirement that
a player can be in at most one pairing, expressed as:

$$
\sum_{i=1}^{k}p_{ik} + \sum_{i=k+1}^{N}p_{ki} = 1,\quad k=1 \ldots N.
$$

The other properties we desire of the rounds we introduce not as hard
constraints, but instead as coming with some penalised weight. That is, including a
player pairing that violates one of the properties noted above is penalised.
The total weight of the round is then minimised as the objective of the
program: 

$$
  \min \sum_{i,j} w_{ij}p_{ij}.
$$

The weight of pairing of players $i$, $j$, that is $w_{ij}$, comprises the
following components:

- To prevent repeated pairing, in the round $R$, we add a weight to the pair $i,j$
  that is dependent on previous rounds:

  $$ 
  w^P_{ij} = \sum_{r=1}^{R-1} w_{ijr},
  $$

  with the weight due to the previous $r$th round being:

  $$
    w_{ijr} = 
    \begin{cases} 
    c_{\mathrm{last}}& \text{if players } i,j \text{ paired in round } r = R-1 \\
    c_{\mathrm{recent}}   & \text{if players } i,j \text{ paired in round } r <  N_\mathrm{recent} \\
    0       & \text{otherwise}
    \end{cases}
  $$

  (It should be noted that this weight also applies to the decision variables
  with repeated subscripts, the $p_{ii}$, which are used to track when a player
  is excluded. In this case, this weight creates a disincentive to repeatedly
  excluding the same player.) 

- To limit pairs in the same organisation, we add the weight 

  $$ 
  w^G_{ij} = 
    \begin{cases} 
    c_\mathrm{group}& \text{if players } i,j \text{ in same group}, \\
    0       & \text{otherwise}.
    \end{cases}
  $$

- To penalise excluding players, we add the weight

  $$ 
  w^E_{ij} = 
    \begin{cases} 
    c_{\text{excluded}} & \text{if } i=j, \\
    0       & \text{otherwise}.
    \end{cases}
  $$

- To limit the number of players who are placed in a repeated role (organiser or coffee buyer), we add:

  $$
    w^R_{ij} =  
    \begin{cases} 
    c_{\text{role}} & \text{if players } i,j \text{ were in the same role last round}, \\
    0       & \text{otherwise}.
    \end{cases}
  $$

- To give the initiative's organiser some additional control, we also allowed an
  "override" weight to be added to the weight of any pair. This could be useful
  if the organiser wishes to either incentivise or disincentivse a specific pairing (i.e. PhD students only meeting other students).


The various constants (the $c$ parameters) could, in principle, be tuned to
express the initiative's relative importance of a particular
property - for example if pairings within organisations was not as important to
avoid as changing the role of the player in each round. However in this
iteration of the program, we have left them fixed at sensible values to
simplify the user interface.

Once a solution has been found, the list of pairings is saved to a CSV file.
This can than be used to send emails to the participants, and used in 
future rounds to determine weightings.


# Acknowledgements

We acknowledge support from Jaimie Cleeland and Philippe Ziegler for the
initial nudge and encouragement to start the process. Also the Overland Track
for facilitating collaboration and the fruition of the solution.

# References
