

   Problem I – Insects, Mathematics, Accuracy, and Efficiency
                             Author : Giovanna Kobus Conrado, Brasil


Cleaning up the input
The first step here is to clean up the input by considering only the points that are vertices of
the convex hull. Since the convex hull is the smallest convex polygon containing all the points,
any point inside the convex hull can be ignored.
After this cleanup, the number of points that we need to consider is reduced. Intuitively, the
resulting number might be considerably lower than the original number of points in input.
One way to come up with a bound is through experimentation. For example, counting the
number of vertices on the convex hull of all integer points in a circle with a radius of R =
10000. This would shows that for our biggest circle the convex hull has ≈ 1600 vertices.
                               2
Alternatively, a bound of O(R 3 ) vertices can be derived with more work, as discussed in
https://codeforces.com/blog/entry/62183.
Note: when computing the convex hull make sure to remove collinear points (otherwise, the
hull can potentially keep all the points from the input).

Solving the problem
We need to add a point p to a set of points to maximize the convex hull while being constrained
by a circle. It’s evident that the point maximizing the area of the new convex hull will always
lie on the border of the circle.
For each vertex v of the original convex hull, consider the segment of the circle in which adding
the new point p excludes v from the new convex hull. This segment can be found by intersecting
the circle with the lines extending from the edges of the polygon adjacent to v.




The 2024 ICPC Latin America Championship
By performing this process for every vertex, we partition the circle into 2N segments, each
representing a unique set of vertices covered if p is added in that segment.




We solve the problem for each segment individually. Finding the point that maximizes the
area of the convex hull is equivalent to maximizing the area of the triangle defined by the
last and first uncovered vertices. As the base of the triangle is fixed, our goal is to maximize
the height, which corresponds to finding the intersection points between the circle and the line
perpendicular to the base of the triangle. All such points can be found through straightforward
primitives.




For each segment, we find the candidate point, generate the convex hull for the new set of
points, and calculate the area, resulting in an O(N 2 log N ) approach.

A numerically stabler approach
The previous approach involves computing the intersection points of lines with the circle, as
well as using those intersection points to figure out the first/last uncovered vertices. Ensuring
numerical stability for this approach might be challenging.
Alternatively we can try all pairs of “diagonals” in the convex hull. All the N 2 “cut areas” can
be computed efficiently and fully in integers, as the original points all have integer coordinates.
The answer will be the maximum of trying to add to these areas, a single triangle which has
to be computed in floating point.
The key insight here is realizing that we don’t need to repeatedly compute the area of the
convex hull. Instead, the area can be updated in O(1) when adding/removing a single vertex.
This means that as we iterate over all pairs of diagonals, we can keep a “running area” and
add to it the area of the triangle formed by the diagonal and the point perpendicular to it in
the circle. This results in an O(N 2 ) approach.
Since such triangles might represent the entire solution (e.g.: for a case with N = 2, where the
two integer vertices of the triangle are given as input), the overall error of the solution depends
on the accuracy of computing this single triangle area. Skinny triangles are numerically ill
conditioned, but for any triangle with coordinates up to 10000, absolute error in computation
should be at most 10−7 for double and 10−11 for long double. Since minimum answer for any
                  4
case N ≥ 2 is 102 , that is a maximum relative error of 10−11 for double and 10−15 for long
double.

The 2024 ICPC Latin America Championship
A faster approach
Notice that combining the two insights above we can solve the problem in O(N log N ) time.
If instead of iterating on the N 2 diagonals we use the 2N critical segments defined in the first
approach and update a “running area” that starts with the area of the original convex hull and
is updated in O(1) as we adjust first/last uncovered vertices while iterating on the segments.
The complexity of the solution is then dominated by the cost of convex hull calculation and
sorting the critical points.
Again, ensuring numerical stability for this approach might be challenging.