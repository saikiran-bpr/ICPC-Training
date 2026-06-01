

                        Problem C – Clever Cell Choices
                            Author : Miguel Angel Ortiz Merida, Bolivia



Analyzing the game
If there is a perfect matching in the graph formed by the empty cells, then the second player
wins. Otherwise, the first player wins.
Let’s consider the scenario where we have found a perfect matching in the grid. In this case,
no matter which empty cell the first player selects, the second player can always place a stone
on the cell matched to the one chosen by the first player. This guarantees a win for the second
player because every empty cell is matched in the perfect matching, ensuring that there is
always a valid move available.
If there is no perfect matching, we find a maximum matching in the graph. Then, the first
player selects an empty cell that is not matched. Subsequently, the first player adopts the
strategy of always choosing an empty cell matched to the one selected by the second player.
This strategy ensures that the first player can always make a move and ultimately win the
game. This is because if the second player ever chooses an empty cell that is not matched
during the game, it implies the existence of a path starting at an unmatched cell, passing
through zero or more pairs of matched cells, and ending at an unmatched cell. In such a case,
we could increase the cardinality of the matching by shifting the matching in one direction
along the path, indicating that the matching found initially was not of maximum cardinality.



The 2024 ICPC Latin America Championship
Counting winning starting cells
Following from the analysis above, winning starting cells are the empty cells that do not belong
to every maximum matching. A cell belongs to every maximum matching if max matching in
G and “G without that cell ” differ.
Given the input constraints (1 ≤ N, M ≤ 50) we could simply run O(N M ) matchings √ using an
                                                                                2 2
efficient algorithm such as Hopcroft-Karp / Dinitz for a total complexity of O(N M N M ).


Faster approach

A slightly faster approach is running one BFS per empty cell after calculating an initial match-
ing.
After the first flow/matching, we work on a max-matching residual network to test nodes one by
one. If the node under consideration is unmatched, then it does not belong to every matching.
Otherwise, we try to modify the flow/matching by passing flow against that matching edge
through a cycle. We should find such a path if and only if there is a max matching without
that node.
For this approach, the final complexity with an efficient matching algorithm is O(N 2 M 2 ).


Even faster approach

Another way to find the cells that do not belong to every maximum matching is by running
two max flows.
We can find the “leftmost” and “rightmost” cuts, which are those vertices “reachable from
the source” and “that reach the sink” in the final residual network in terms of flow. This
information tells us which nodes are always in some side of the matching.
This can be proved by looking at the symmetric difference of current matching and a hypo-
thetical matching not containing a certain vertex.
                                                         √
With this approach, the final complexity reduces to O(N M N M ).