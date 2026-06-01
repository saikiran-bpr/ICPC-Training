

                      Problem H – Harmonic Operations
                          Author : Agustı́n Santiago Gutiérrez, Argentina


First of all we study the composition of allowed transformations.
We can convert L(t, D) transformations into equivalent R(t, D0 ) transformations by utilizing
the fact that L(t, D) = R(t, |t| − D).
When composing a series of operations like the ones given, the resulting total transformation
is either a single rotation, or a single inversion followed by a single rotation. The rule for
composing two of these total transformations is quite simple and easy to find and check by
examples:

   • R(t, a) = t0 followed by R(t0 , b) is R(t, a + b)


The 2024 ICPC Latin America Championship
   • I(t) = t0 followed by I(t0 ) is the identity, “no transformation” or simply R(t, 0)

   • R(t, a) = t0 followed by I(t0 ) is the same as I(t) = t00 followed by R(t00 , |t| − a)

   • I(t) = t0 followed by R(t0 , a) simply stays like that and is a possible total transformation

The rule for the inverse transformation is also simple: the inverse of R(t, a) is R(t, |t| − a) and
any transformation of the form I(t) = t0 followed by R(t0 , a) is its own inverse.
These properties define the dihedral group: https://en.wikipedia.org/wiki/Dihedral_
group. Previous knowledge of group theory, more specifically of the dihedral group itself,
can help in finding this problem’s solution faster, but such special knowledge is not a prerequi-
site for solving the problem as no advanced group-theoretic result is used, only the structure of
the particular dihedral group which is quite ad hoc and can be discovered by doing examples
and reasoning “how much information must I keep”, so not specially harder or different than
very similar techniques used in segment tree or other competitive programming problems where
a range of items is aggregated.
After all that, something to notice is what happens if string S is a power S = Ak , that is, S is
formed by concatenating k ≥ 2 identical copies of string A. Then, for any transformation f ,
the resulting new string after applying f will still be k copies of a single string, and that string
is f (A). That is, f (S) = f (A)k .
Thus for S = Ak , a sublist of transformations leaves S fixed if and only if it leaves A fixed. We
can then start by computing the largest k such that we can write S = Ak (possibly k = 1), which
is a standard and classical problem efficiently solvable using KMP or other string techniques.
Then by the previous analysis the test case answer does not change if we assume input is simply
A instead of S, so we have reduced the problem to the case where the string is not a power
(i.e. we can only write S = Ak if k = 1). Note that this effectively shrinks the actual |t| that
we will use when composing transformations and computing inverse transformations.
The key thing one might conjecture is that once we have a string of length N that is not a
power, then all the 2N possible transformations actually give different strings when applied to
S. This is clearly true for the N rotations, as if two different rotations give the same string it
is easily proved that the string is S = Ak with k > 1. But it might fail for the inversions: there
might be some I(S) followed by R(S, a) that leaves S fixed. This never happens for a string
such as “cosa”, but it does happen for a string such as “casa”: even though all its rotations
are different, I(“casa”) = “asac” followed by R(“asac”, 1) = “casa” does not change the
string. The critical property of “casa” is that its inversion “asac” is identical to one of its
rotations, in this case R(“casa”, 3).
Critically, there can never be two distinct values a, b such that both I(S) = S 0 followed by
R(S 0 , a) and I(S) = S 0 followed by R(S 0 , b) fix S. If it were the case, applying one after the
other would also not change S, but doing so produces a non-trivial rotation, and since the
string was not a power, this is a contradiction. So after initially reducing the string to be a
non-power, there will be at most two total transformations that fix it: the trivial transformation
R(S, 0) which always works, and possibly one transformation of the form I(S) = S 0 followed
by R(S 0 , a), precisely when one of the rotations of the string matches its reverse. This can also
be checked efficiently by duplicating the string and then using any standard string matching
algorithm like KMP.
Once we have this structure understood, we need to count the number of pairs. A pair i, j
will work only if performing the composition (in order) of all the transformations in the [i, j]
range gives one of the (at most two) working transformations as a total result. The number
of pairs can be counted in linear time using an histogram and the same idea as “prefix-sum”:
if we compute the net transformation of every prefix [0, i) in P (i), then for a range [i, j) the
net transformation in range is simply the inverse of P (i) followed by P (j). So for a fixed value

The 2024 ICPC Latin America Championship
of either i or j (lets say j), it is simple to identify which are the one or two possible total
transformations that work as P (i), and if we are processing left to right (or right to left if we
are fixing i) we can have already counted in an histogram array the total number of previous
indexes i < j such that P (i) equals any specific value we desire. So adding all of these counts
together for all values of j will give the final answer.
Using efficient string algorithms like KMP, the final time complexity is linear in input size
O(|S| + K).
Note that if we don’t start by reducing the string to a non-power, many rotations and trans-
formation work. The set of precisely which of the 2N transformations work can be computed
efficiently with the same string algorithms: we need to know which rotations match the string
or its reverse, which is practically the same info we compute when reducing to non-power.
However, in the last counting step, for each j we would have to check a linear number of rele-
vant P (i) values in the histogram, leading to quadratic complexity. The reduction ensures that
we just have to check two candidates at most.