# Rego unit tests — run with: opa test m3-security/policies
package lens.authz_test

import data.lens.authz

_candidates := ["LE-0001", "LE-0010", "LE-0020", "LE-0030"]

test_group_risk_sees_all if {
	v := authz.visible_groups with input as {
		"role": "group_risk",
		"candidate_groups": _candidates,
	}
	v == {"LE-0001", "LE-0010", "LE-0020", "LE-0030"}
}

test_rm_sees_only_portfolio if {
	v := authz.visible_groups with input as {
		"role": "relationship_manager",
		"portfolios": ["LE-0020", "LE-0030"],
		"candidate_groups": _candidates,
	}
	v == {"LE-0020", "LE-0030"}
}

test_rm_allow_in_portfolio if {
	authz.allow with input as {
		"role": "relationship_manager",
		"portfolios": ["LE-0001"],
		"group": "LE-0001",
	}
}

test_rm_deny_outside_portfolio if {
	not authz.allow with input as {
		"role": "relationship_manager",
		"portfolios": ["LE-0001"],
		"group": "LE-0020",
	}
}

test_group_risk_allows_any if {
	authz.allow with input as {"role": "group_risk", "group": "LE-9999"}
}
