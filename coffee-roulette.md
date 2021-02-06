---
title: 'Collete: A networking programme for coffee-pairings to build research connections'
tags:
  - Python
  - fisheries
  - networking
  - coffee-pairings
authors:
  - name: David E. Horsley 
    orcid: TODO
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
account leaving or joining the group. The software contains functionality for
integration into an email / exchange platform (? not sure how to phrase this - ?) for automation of email sending.

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
ability to integrate with SQLite for storage of pairings in a database that
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

To efficiently produce pairings with the desired properties, we first
formulate the problem as an integer program.

If we have N "players" in the round, labeled $1\ldots N$, our decision variables are the
binary values 

$$
p_{ij} \in \{0,1\}, \quad 1\le i \le N,\ i \le j \le N,
$$

denoting player $i$ and $j$ are to be paired in the current round. The
variables with the same index, $p_{ii}$, are included to denote the player
$i$ has been excluded from the round.

Our one constraint is that players are included in only one pair, or removed from the round:

$$
\sum_{i=1}^{k}p_{ik} + \sum_{i=k+1}^{N}p_{ki} = 1,
$$

and the other properties we desire of the round are introduced not as hard
constraints, but as coming with a cost when violated and the total "cost" of
the round is to be minimised. This gives rise to the objective function for
the program:

$$
  \min \sum_{i,j} w_{ij}p_{ij},
$$

with the weights $w_{ij}$ as follows:

In round R, we add a weight to pair $i,j$:

$$ 
w^P_{ij} = \sum_{r=1}^{R-1} w_{ijr},
$$

Where the sum is over previous rounds with:

$$
  w_{ijr} = 
  \begin{cases} 
   c_{\mathrm{last}}& \text{if players } i,j \text{ paired in round } r = R-1 \\
   c_{\text{recent}}   & \text{if players } i,j \text{ paired in round } r <  N_\text{recent} \\
   0       & \text{otherwise}
  \end{cases}
$$

We also add a term to limit pairs in the same group
$$ 
w^G_{ij} = 
  \begin{cases} 
   \delta& \text{if players } i,j \text{ in same group}, \\
   0       & \text{otherwise},
  \end{cases}
$$

and to penalise excluding players we add the weight

$$ 
w^E_{ij} = 
  \begin{cases} 
   c_{\text{not pairing}} & \text{if } i=j, \\
   0       & \text{otherwise}.
  \end{cases}
$$


# Citations

Citations to entries in paper.bib should be in
[rMarkdown](http://rmarkdown.rstudio.com/authoring_bibliographies_and_citations.html)
format.

If you want to cite a software repository URL (e.g. something on GitHub without a preferred
citation) then you can do it with the example BibTeX entry below for @fidgit.

For a quick reference, the following citation commands can be used:
- `@author:2001`  ->  "Author et al. (2001)"
- `[@author:2001]` -> "(Author et al., 2001)"
- `[@author1:2001; @author2:2001]` -> "(Author1 et al., 2001; Author2 et al., 2002)"


# Acknowledgements

We acknowledge support from Jaimie Cleeland and Philippe Ziegler for the initial nudge and encouragement to start the process. Also the Overland Track for facilitating collaboration and the fruition of the solution.

# References

# Summary

Effective scientific collaboration is necessary to make efficient use of limited funding to solve issues common across fisheries science. Instigating and facilitating networking across multiple government and research organisations, and disciplines is one way of improving the chances of new collaborations forming. With a lack of in-person conferences and inter-group workshops in 2020, there was an opportunity to find a new way to create links between fisheries scientists in organisations based in Hobart. A common roadblock within government departments and research organisations is access to simple, free, open-access software to facilitate networking that does not increase administration burdens. The software randomly pairs people from different organisations, for multiple rounds of coffee, while taking into account leaving or joining the group. The software contains functionality for integration into an email / exchange platform (? not sure how to phrase this - ?) for automation of email sending.

# Statement of need

`Colette` is a Python package for facilitating networking. `Colette` allows for random pairings of individuals from multiple organisations in a population. Pairings are favoured between individuals of different organisations, and recent pairings between individuals are penalised so that individuals meet as many individuals within the population as possible before re-pairings occur. Pairings with self are removed from the round. Each run of the software produces one round of pairings. The novel aspect of the programme is that multiple rounds of pairings are possible and produce pairings based on prior rounds. This allows for ease of tracking pairings, and assurance that individuals are not being randomly assigned the same partner each round. Pairings with self, or recently paired individuals are penalised, Individuals can leave and re-join the population with no penalty, and a reduced likelihood of pairing with their last pair when they return. The package allows for integration with a mail provider to automate emails if required or desired.

Python was chosen as it enables a user-friendly output (.csv files) and the ability to integrate with SQLite for storage of pairings in a database that can then be joined with other databases. Python is a flexible and popular programming language, so there are opportunities to build and develop the package within the data / programming / nerd (?) community.

`Colette` is designed to be used by anyone wanting to facilitate collaboration pairings. It is currently being used in Hobart to facilitate coffee pairings between fisheries scientists at the University of Tasmania, the Commonwealth Scientific and Industrial Research Organisation (CSIRO), the Australian Antarctic Division (within the Commonwealth Department of Agriculture, Water, and the Environment), and the Tasmanian State Department for Primary Industry, Parks, Wildlife and the Environment (DPIPWE), and has already facilitated collaborations between interdisciplinary scientists. The software will also be used by the Institute of Marine and Antarctic Studies (IMAS) postdoctoral researchers for regular pairings, and speed-networking events.

# Mathematics

`Colette` uses some decision / matrix maths.

Single dollars ($) are required for inline mathematics e.g. $f(x) = e^{\pi/x}$

Double dollars make self-standing equations:

$$\Theta(x) = \left\{\begin{array}{l}
0\textrm{ if } x < 0\cr
1\textrm{ else}
\end{array}\right.$$

You can also use plain \LaTeX for equations
\begin{equation}\label{eq:fourier}
\hat f(\omega) = \int_{-\infty}^{\infty} f(x) e^{i\omega x} dx
\end{equation}
and refer to \autoref{eq:fourier} from text.

# Citations

Citations to entries in paper.bib should be in
[rMarkdown](http://rmarkdown.rstudio.com/authoring_bibliographies_and_citations.html)
format.

If you want to cite a software repository URL (e.g. something on GitHub without a preferred
citation) then you can do it with the example BibTeX entry below for @fidgit.

For a quick reference, the following citation commands can be used:
- `@author:2001`  ->  "Author et al. (2001)"
- `[@author:2001]` -> "(Author et al., 2001)"
- `[@author1:2001; @author2:2001]` -> "(Author1 et al., 2001; Author2 et al., 2002)"

# Figures

Figures can be included like this:
![Caption for example figure.\label{fig:example}](figure.png)
and referenced from text using \autoref{fig:example}.

Figure sizes can be customized by adding an optional second parameter:
![Caption for example figure.](figure.png){ width=20% }

# Acknowledgements

We acknowledge support from Jaimie Cleeland and Philippe Ziegler for the initial nudge and encouragement to start the process. Also the Overland Track for facilitating collaboration and the fruition of the solution.

# References

>>>>>>> 8f1862f862e14e5214a62cb716d1a0841f4539a1
---