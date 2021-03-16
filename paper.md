---
title: 'Collete: A networking programme for coffee-pairings to build research connections'
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
increase administration burdens. The software randomly pairs people from
different organisations, for multiple rounds of networking, while taking into
account individuals leaving, joining, or re-joining the group. The software contains functionality
to automatically email participants based on pre-constructed templates.

# Statement of need

`Colette` is a Python package for facilitating networking. `Colette` allows
for random pairings of individuals from multiple organisations in a
population. Pairings are favoured between individuals of different
organisations, and recent pairings between individuals are penalised so that
individuals meet as many individuals within the population as possible before
re-pairings occur. Each run of
the software produces one round of pairings. The novel aspect of the
program is that multiple rounds of distinct pairings are possible and are generated
based on prior rounds. For example, pairings are unlikely reoccur until individuals have been paired with all others in the population. This allows for ease of tracking pairings,
and assurance that individuals are not being randomly assigned the same
partner each round. Individuals can leave and re-join the population with no penalty,
and a reduced likelihood of pairing with their last pair when they return.
The package allows for integration with a mail provider to automate emails if
required or desired.

Python was chosen due to the author's familiarity with the language and the
number of high quality operations research packages available.

`Colette` is designed to be used by anyone wanting to facilitate
collaboration pairings. It is currently being used in Hobart to facilitate
coffee pairings between fisheries scientists at the University of Tasmania,
the Commonwealth Scientific and Industrial Research Organisation (CSIRO), the
Australian Antarctic Division (within the Commonwealth Department of
Agriculture, Water, and the Environment), and the Tasmanian State Department
for Primary Industry, Parks, Wildlife and the Environment (DPIPWE), and has
already facilitated collaborations between interdisciplinary scientists. The
software will also be used by the Institute of Marine and Antarctic Studies
(IMAS) postdoctoral researchers for regular pairings, and speed-networking
events.

# Method

Here we outline the approach to creating pairings taken by `colette`.

The main insight of this work is that we may reduce the problem
to one with well established efficient algorithms for finding solutions, 
by formulating the problem as an integer program. 

To write the problem as an integer program, if we assume we have N "players" in
the round, labeled $1\ldots N$, we let

$$
p_{ij} \in \{0,1\}, \quad 1\le i \le N,\ i \le j \le N,
$$

denote that player $i$ and $j$ are to be paired in the current round.

Here we have used variables with the same index, $p_{ii}$, to denote that the
player $i$ has been excluded from the round. This will be useful later when we
formulate our objective function.

Our one constraint on the decision variables $p_{ij}$ come from the requirement that
a player can be in at most one pairing, expressed as

$$
\sum_{i=1}^{k}p_{ik} + \sum_{i=k+1}^{N}p_{ki} = 1,\quad k=1\ldotsN.
$$

The other properties we desire of the rounds are introduced not as hard
constraints, but as a penalised cost. For example, including a player pairing
that violates one of the properties is penalised. The total cost of the round
is then to be minimised as the objective of the program. That is:

$$
  \min \sum_{i,j} w_{ij}p_{ij}.
$$

The cost of including players $i$, $j$, that is $w_{ij}$, comprises the
following components:

- To prevent repeated pairing, in a round R, we add a weight to pair $i,j$
  dependent on previous rounds:

  $$ 
  w^P_{ij} = \sum_{r=1}^{R-1} w_{ijr},
  $$

  with the weight due to the $r$th round being:

  $$
    w_{ijr} = 
    \begin{cases} 
    c_{\mathrm{last}}& \text{if players } i,j \text{ paired in round } r = R-1 \\
    c_{\mathrm{recent}}   & \text{if players } i,j \text{ paired in round } r <  N_\mathrm{recent} \\
    0       & \text{otherwise}
    \end{cases}
  $$

- To limit pairs in the same group, we add the weight 

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



With the problem stated as a linear integer program, it can now be approached using
standard combinatorial optimisation methods.  In this work we find solutions to
the pairing problem using the COIN-OR CBC [@coin-or-cbc] solver via the Python
MIP package [@python-mip]. The CBC solver uses the Branch-and-Cut method to solve
the program; relaxing the integer constraints and solving the resulting linear
program, then using cutting planes to tighten the integer constraints.

The various constants (the $c$ parameters) could in principle be tuned to
express the initiative's organiser's relative importance of a particular
property, however we leave them fixed at some sensible values to simplify the
user interface.

# Acknowledgements

We acknowledge support from Jaimie Cleeland and Philippe Ziegler for the
initial nudge and encouragement to start the process. Also the Overland Track
for facilitating collaboration and the fruition of the solution.

# References
