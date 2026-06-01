

                           Problem J – Joys of Trading
                          Author : Agustı́n Santiago Gutiérrez, Argentina


This problem is a greedy sorting problem that invites a lot of failed greedy attempts.
If there were no restrictions on the total number of hours invested by each village, then obviously
the global minimum is reached if for each resource, we make the village that is faster at that
resource produce the whole of it, in sufficient amount for both villages.
This invites one to greedily try something like that but only while there are enough person-
hours available, and finally completing all remaining work with the other tribe. Unfortunately,
it is not the case in general that a resource should be done by the village that does it faster.
                                             Ai
The correct greedy is to sort resources by B  i
                                                . Then, it is the case that there will be some
cutting point in this sorted array of resources such that village A produces the prefix before
the cut, and village B produces the suffix after the cut. Note that the cut might be placed
at any continuous position and thus might be “inside some resource”, as happens in the first
example where the cut is “0,5 units into food”.
The proof is by reductio ad absurdum: take a solution that is “as close as possible” to having
A produce a prefix and B a suffix in the sorted array. Now assume that in this sorted array,
there are two different resources having indexes i < j, and such that B produces a quantity
x > 0 of resource i, while A produces a quantity y > 0 of resource j. If we change village B
so that it uses  · Bi less person-hours on resource i, and redirect those person-hours so that B
uses them to produce resource j instead, we will get J = ·B  Bj units of resource j, while losing
                                                                i


 of resource i.
                                     Ai       A         Bi   Ai                          Ai
Because of the sort criteria we have Bi
                                        ≤ Bjj , that is Bj
                                                           ≥ A j
                                                                 , and from this J ≥  · A j
                                                                                             , so
                       Ai
we get more than  · A  j
                          units of resource j, a quantity that takes village A a total of  · Ai
person-hours to produce. If we now redirect those  · Ai person-hours of village A to produce
resource i instead, we get  units of resource i.
For small enough , we are sure to be able to make all of these changes and get a valid solution.
So, after these changes, we end up with no less resources, while using exactly the same person-
hours in each village, and we move closer to having all work of A being a prefix and B being a
suffix, which is absurd because we chose one that was as close as possible.
Once we have that result established, it is possible to try all N resources to see if the cut is
in that resource. When moving from cut i to i + 1 it is simple to update the total cost of A
producing every resource in [0, i) and the total cost of B producing every resource in [i + 1, N ).
Then only resource i remains, and a certain amount of available person-hours for each of A
and B is known, so this resource being the only left can be greedily solved: use the village that
produces it more efficiently, until the whole resource is produced or available person-hours run
out, and then switch to the other one.

The 2024 ICPC Latin America Championship
That way, all cuts can be tried and the cost for all of them computed in O(N log N ) time, so
that the best one is finally returned. The implementation is very simple and the most difficult
part of the problem is probably coming up with the correct sort among many possible incorrect
greedy alternatives.
An interesting corollary of this problem is that specializing and trading is efficient: an op-
timal solution always exists where there is at most one resource that is produced by both
villages.