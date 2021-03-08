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
date: "`r format(Sys.time(), '%d %B, %Y')`"
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
roadblock within government departments and research organisations is access
to simple, free, open-access software to facilitate networking that does not
increase administration burdens. The software randomly pairs people from
different organisations, for multiple rounds of coffee, while taking into
account leaving or joining the group. The software contains functionality
automatically emailing participants based on templates.

# Statement of need

`Colette` is a Python package for facilitating networking. `Colette` allows
for random pairings of individuals from multiple organisations in a
population. Pairings are favoured between individuals of different
organisations, and recent pairings between individuals are penalised so that
individuals meet as many individuals within the population as possible before
re-pairings occur. Pairings with self are removed from the round. Each run of
the software produces one round of pairings. The novel aspect of the
programme is that multiple rounds of pairings are possible and produce
pairings based on prior rounds. This allows for ease of tracking pairings,
and assurance that individuals are not being randomly assigned the same
partner each round. Pairings with self, or recently paired individuals are
penalised, Individuals can leave and re-join the population with no penalty,
and a reduced likelihood of pairing with their last pair when they return.
The package allows for integration with a mail provider to automate emails if
required or desired.

Python was chosen as it enables a user-friendly output (.csv files) and the
ability to integrate with for storage of pairings in a database that
can then be joined with other databases. Python is a flexible and popular
programming language, so there are opportunities to build and develop the
package within the data / programming / nerd community.

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

Our goal is to formulate an efficiently method
for generating pairings with the desired properties. 
The main insight of this work is that we may formulate the problem as an
integer program.

To do this we begin with some notation. If we have N "players" in the round,
labeled $1\ldots N$, we let
$$
p_{ij} \in \{0,1\}, \quad 1\le i \le N,\ i \le j \le N,
$$

denote that player $i$ and $j$ are to be paired in the current round. The
Here we have used variables with the same index, $p_{ii}$, to denote that the
player $i$ has been excluded from the round. This will be useful later.

Our one constraint on the decision variables come from the requirement that players
can only be in one pair or are from the round, expressed as

$$
\sum_{i=1}^{k}p_{ik} + \sum_{i=k+1}^{N}p_{ki} = 1.
$$

The other properties we desire of the rounds are introduced not as hard
constraints, but including a player pairing that violates one of the properties
comes with a cost. The total cost or weight of the round is then to be
minimised as the objective of the program. That is:

$$
  \min \sum_{i,j} w_{ij}p_{ij}.
$$

The weight of including players $i$, $j$, that is $w_{ij}$, comprises the
following components:

- To prevent repeated pairing, in round R, we add a weight to pair $i,j$:

  $$ 
  w^P_{ij} = \sum_{r=1}^{R-1} w_{ijr},
  $$

  Where the sum is over previous rounds with:

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



The problem can then be approached by standard integer programming methods.
In this work we find solutions using the COIN-OR Branch-&-Cut CBC [@coin-or-cbc] solver via
the Python MIP package [python-mip].

The various constants (the $c$ parameters) could in principle be tuned to
express the initiative's organiser's relative importance of a particular
property, however we leave them fixed at some sensible values to simplify the
user interface.

# Acknowledgements

We acknowledge support from Jaimie Cleeland and Philippe Ziegler for the
initial nudge and encouragement to start the process. Also the Overland Track
for facilitating collaboration and the fruition of the solution.

# References
