# Authorization as code (M3) — who may see which counterparty exposures.
#
# Two roles (docs/engineering-practices.md § Policy as Code):
#   * group_risk          — sees every counterparty group
#   * relationship_manager— sees only the groups in their own portfolio
#
# The app consults this policy (via `opa eval`) to scope every read; the policy
# lives OUTSIDE the application code and is unit-tested with `opa test`.
#
# Input contract:
#   {
#     "role": "group_risk" | "relationship_manager",
#     "portfolios": ["LE-0001", ...],        # groups the user manages (RM)
#     "candidate_groups": ["LE-0001", ...],  # all top-level groups in scope
#     "group": "LE-0001"                     # single-resource check (optional)
#   }

package lens.authz

# --- the visible set the app filters reads by ------------------------------- #

# group_risk sees every candidate group
visible_groups contains g if {
	input.role == "group_risk"
	some g in input.candidate_groups
}

# a relationship_manager sees only candidate groups in their portfolio
visible_groups contains g if {
	input.role == "relationship_manager"
	some g in input.candidate_groups
	g in input.portfolios
}

# --- single-resource decision (e.g. "may this user open group X?") ---------- #

default allow := false

allow if input.role == "group_risk"

allow if {
	input.role == "relationship_manager"
	input.group in input.portfolios
}
