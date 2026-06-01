

                          Problem F – Fair Distribution
                              Author : Victor de Sousa Lamarca, Brasil


To determine whether a fair distribution of blueprints is possible, we first need to consider all
possible total height differences that can arise due to the ground floors. We need to consider
every way to partition the blueprints into two non-empty sets, denoted by A and B. The total
height difference due to ground floors for
                                        P such a partition would be the difference between the
 P of ground floor heights in set A ( i∈A Gi ) and the sum of ground floor heights in set B
sum
( i∈B Gi ).
These unavoidable differences due to ground floors represent the contributions to the overall
height difference between Alice and Bob’s buildings. Once the blueprints are assigned, these
differences are fixed, and the number of residential floors chosen will need to compensate for
them.
The key question is: which kinds of total height differences are achievable depending on how
the number of residential floors is set?
It turns out that a fair distribution is possible if and only if the GCD of the heights of resi-
dential floors divides any of the previously listed height differences. This comes from Bezout’s
identity, or alternatively from understanding of Euclid’s algorithm and some math on modular
arithmetic.
All that’s left is efficiently listing all possible total height differences due to ground floors. We
exploit the fact that the sum of the heights of the ground floors of all blueprints is at most
O(N ), where N is √   the number of blueprints. This implies that the number of distinct ground
floor heights is O( N ), allowing us to optimize the knapsack        √ algorithm. By adapting the
knapsack algorithm, we can achieve a final complexity of O(N N ). More details on optimizing
the knapsack algorithm can be found in page 254 of https://cses.fi/book/book.pdf or
https://codeforces.com/blog/entry/59606.




The 2024 ICPC Latin America Championship