



                          Problem A – Almost Aligned
                                   Author : Daniel Bossle, Brasil


Ternary search for the value t that results in the minimum bounding box area might be the
most intuitive approach, but it is not correct. We are minimizing the product of two convex
curves, which is not necessarily convex.
The area is:

         (max(X + VX · t) − min(X + VX · t)) · (max(Y + VY · t) − min(Y + VY · t))

These two dimensions follow a piecewise linear curve, which we can obtain with the Convex
Hull Trick, and then analyze piece by piece.
Notice that the optimum value is always “in one extreme” (that is, it always occurs either at
t = 0 or at a “changepoint” of one of the piecewise linear functions).
Total time is O(N log N ).