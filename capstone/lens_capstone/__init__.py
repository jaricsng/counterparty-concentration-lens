"""Capstone — scale & reflect.

A Spark-equivalent of the M1 loader (same FIBO triples, produced by a distributed
job) plus the "what this is NOT" scope statement. The row -> triples mapping is a
pure, Spark-free function (:mod:`lens_capstone.triples_map`) so its output can be
proven identical to the M1 loader without standing up a Spark cluster.

Learning prototype on SYNTHETIC data. Production-shaped, not production-hardened.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
