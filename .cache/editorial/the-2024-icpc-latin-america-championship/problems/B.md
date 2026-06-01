

                       Problem B – Beating the Record
                          Author : Agustı́n Santiago Gutiérrez, Argentina



Solution description
The expected solution is exhaustive search over the space of possible “global strategies”, and
thus the very small limit on N . A lot of the difficulty in this problem should be the correct
modeling of what a “global strategy” for the speedrunning process is. It is fairly easy to assume
false hypothesis, like all the following:

  1. You will only ever restart the game when the probability to finish this run in under T
     seconds drops to zero.

  2. We can do naive dynamic programming to solve the problem, and the state for that just
     needs to keep track of the current actual time in game (an integer) and in which of the
     N hard sections we currently are.

  3. We can choose a fixed strategy for each of the N levels (including the different combina-
     tions of restarting the game depending on results) and then brute force all combinations.

These approaches are false in general. A counterexample to 1) is:



The 2024 ICPC Latin America Championship
1 1000 1
50 900 900 1 500 800

Here, a single full playtrough of the game is guaranteed to beat the world record of T = 1000.
The first strategy takes 901 seconds, and the second one takes 798 on average. However, if
we use the second strategy and also take advantage of instantly restarting the game whenever
we fail the risky strategy, we get an expected 99 fails which only take 1 second each, for an
expected time of 600 seconds. Note crucially that the previous example depends on the value
S = 1 being “small enough” that restarts are worth it, and in fact for S = 4 or larger it is better
not to restart. These kind of effects is what breaks 2): such a DP approach is very tempting,
because the state actually contains “enough information to make the optimal decision” (as it is
quite intuitive that nothing other than current level and elapsed time is relevant). The problem
is how to correctly compute that optimal decision, without looking at the “global strategy”
(that is, without having solved the problem first).
For DP to work we need an order of iteration (i.e. no dependency cycles), and to use only
values that have already been computed. This example shows that the decision of what to
do at a certain game state is not oblivious to the input values and subproblem results of the
previous levels. And of course, the decision also depends on later levels. Because of this, the
author could not find any recursive formula for such simple state. However, there is a way to
solve the problem very efficiently by fixing this issue, which we will explain in a later section.
The failure of assumption 3) points directly at what a “global strategy” is and is not. A
counterexample to 3) is

2 1000 900
50 10 20 50 10 20
10 89 100 5 79 100

For the first level, there is actually just a fifty-fifty split between taking 10 or 20 seconds.
However it takes 900 seconds of game to get to that point, so restarts are very expensive and
are not a good idea while there is still even a 5 percent chance at the record.
At the second level, we want to go for the first strategy if the first level took only 10 seconds,
and for the second strategy when the first level took 20 seconds (riskier, but necessary to get
the record). So which strategy to choose for a level critically depends on the result of attempts
at previous levels, as that changes the in-game time of arrival to the current level.
Thus, we see that a formalization of “global strategy” has to take into account these kind of
“chained-ifs”. For a fixed global strategy, ignoring resets for a while, a natural representation
is a binary tree of possibilities: each node corresponds to a decision to take when arriving at
a hard section, and thus would be labeled with a strategy to select at that point (either first
or second strategy). The two children of each node then correspond to the possible branching
of that run’s “history”, depending on whether the attempted strategy succeeded or failed.
Then crucially, the global strategy can select different strategies on the same game level (which
corresponds to all nodes at the same depth or “level” in the tree) depending on the actual path
of history up to that level (as those different nodes can be labeled with different strategies).
So for 4 levels, there are 15 nodes in this decision tree, and so we have 215 possible strategies
without resets. Finally, adding the possibility of resets into this representation is not too hard:
a reset will always be done right after a decision is made, upon knowing the unfavorable result,
and so corresponds to one of our previous 215 trees but with some pruned branches.
We can actually count all such trees by the recursion:
                               f (n) = 2(f (n − 1)2 + f (n − 1))
                               f (0) = 1

The 2024 ICPC Latin America Championship
The factor of 2 accounts for choosing first or second strategy at the root node, and then once
that is fixed there are f (n − 1) ways to complete the tree if we choose to reset upon bad result
on the root, or f (n−1)2 ways if we choose to continue without resetting at the root. It is trivial
to check that f (4) = 21523360 so only about 20 million strategies have to be checked. The
                                                      2n
actual general solution to the recursion is f (n) = 3 2−1 , which can be checked by induction
but is unnecessary to solve the problem. Interestingly, it proves that the intended solution has
                  N
complexity O(32 ).
The calculation of the expected time for a fixed strategy tree is an interesting exercise in proba-
bility. First, computing the probability of a run beating the record is relatively straightforward,
as once the global strategy is fixed we can just track the probability of arriving at each node
from the start and add up “winning nodes”.
However, to compute the final expected value we will need to compute two values of conditional
expectations for the time to traverse the tree (make a run of the game): an expected time given
that the run is successful in beating the record, and an expected time given that the run fails.
All of these values can be computed with some care by propagating cumulative probabilities
and times from parents to children while branching in the tree, starting from a probability of
1 and S time invested in the root node.
Once we get the global expected time when success eg , expected time when fail eb and prob-
ability of success p, the expected time until winning is eg + ( p1 − 1)eb .
For efficiency and possibly for ease of code, it is best to implement the process of generating
strategies as a simple backtracking over a global vector of “nodes still waiting to be expanded”,
thus completely avoiding storing the actual tree. The starting state is the root node, and the
backtracking always selects the last node in the vector and “branches” itself depending on the
different strategies to choose for that node. For each of those strategies, the corresponding
node is deleted from vector and new nodes are generated for the children nodes and pushed
into vector: either 0 new nodes (for leaf nodes at level N ), 1 (for a choice of strategy that
restarts on a bad outcome), or 2 new nodes (for a strategy that will not restart at that node).
Note that this way during the backtracking, there are actually 4 choices of “strategy” in each
node: we can choose either the first or second strategy of the level, and then we can choose
either not to restart, or to restart if unsuccessful. If one does not notice that restarting upon
successful attempt makes no sense (one should have restarted earlier in that case), these are 6
choices.
Finally, note that N = 5 is already too much for this approach, as there are about 330 strategies.

About numerical stability
If using floating point, care should be put to the possibility of numerical error. All involved
computations should be numerically stable with typical implementations, except for the sub-
traction in the ( p1 − 1) factor of the final formula. This subtraction carries a real risk of
catastrophic cancellation and a significant loss of precision in a case where p is very close to
1. However, in all implementations we tried for this particular problem, it can be proved that
double precision turns out to be enough even when performing this 1−p computation (although
not by a large margin).
This is easily avoided if the code also computes the probability of fail f = 1 − p by directly
accumulating (adding positive probabilities) along the tree, in exactly the same way that we
described p can be computed. Then the formula becomes p1 −1 = fp , and division is a numerically
stable operation. Exponent underflow (in probabilities) or overflow (in the final expected value)
does not seem to be a serious concern, as N = 4 means that the lowest positive probabilities
involved are around 10−8 . Perhaps the best alternative is to just work with integers until the
very final formula eg +( p1 −1)eb , so that the subtraction can be made in an exact way. This can


The 2024 ICPC Latin America Championship
be done easily because the probability calculations of eg , eb , p, f values only leaves integers due
                    1
to the probability 100 factors when adjusting the input percentages. We can get rid of those
factors by “multiplying” the real values by 108 and just doing all computations in integers.
This is equivalent to using a decimal, fixed point representation with 8 digits after decimal
dot, which is enough to exactly represent all values up until the division by p in the very final
formula.

An efficient solution
Even though it is not the intended solution, the problem can be solved with dynamic program-
ming + a binary search trick.
Let dp(i, t) be the expected remaining time when playing optimally, given that we are currently
at level i and have already used t seconds in this run of the game. Note that in our problem
there are O(2N ) possible values of t. Our desired final answer is E = dp(0, S).
It is possible to express dp(i, t) based on the dp(i + 1, t0 ) values and, due to resets, the E =
dp(0, S) value. Crucially, the only dependency that goes “backwards” in time for the recursion
is the dependency on E. Thus, if we fix the value of E by guessing it, it is possible to solve for
all of the other dp(i, t) values, including the dp(0, S) itself, by using the recursive dp formula
replacing any mention of dp(0, S) by the guessed value of E.
The key property (the proof of which is left as an exercise to the reader) is that if our guess for
E was too high, then the computed value dp(0, S) will be lower than E. And conversely, if the
guess E was too low, then the computed value dp(0, S) will be higher than E. Thus we can
continue guessing by using binary search to get the correct value of E to the desired precision.
The complexity is either O(BN T ) or O(B2N ) if only the reachable states are used, where B
is the number of steps of the binary search.