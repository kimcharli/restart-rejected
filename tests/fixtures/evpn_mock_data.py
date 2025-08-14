"""Mock data for EVPN testing."""

from lxml import etree

# Mock EVPN XML responses for different scenarios

HEALTHY_EVPN_RESPONSE = """
<evpn-ip-prefix-database-information>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Accepted</adv-ip-route-status>
        <ip-prefix>192.168.1.1/32</ip-prefix>
        <rd>65001:1</rd>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Accepted</adv-ip-route-status>
        <ip-prefix>192.168.1.2/32</ip-prefix>
        <rd>65001:1</rd>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Accepted</adv-ip-route-status>
        <ip-prefix>192.168.1.3/32</ip-prefix>
        <rd>65001:1</rd>
    </evpn-ip-prefix-database>
</evpn-ip-prefix-database-information>
"""

REJECTED_ROUTES_RESPONSE = """
<evpn-ip-prefix-database-information>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Accepted</adv-ip-route-status>
        <ip-prefix>192.168.1.1/32</ip-prefix>
        <rd>65001:1</rd>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Rejected</adv-ip-route-status>
        <ip-prefix>192.168.1.2/32</ip-prefix>
        <rd>65001:1</rd>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Rejected</adv-ip-route-status>
        <ip-prefix>192.168.1.3/32</ip-prefix>
        <rd>65001:1</rd>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Pending</adv-ip-route-status>
        <ip-prefix>192.168.1.4/32</ip-prefix>
        <rd>65001:1</rd>
    </evpn-ip-prefix-database>
</evpn-ip-prefix-database-information>
"""

EMPTY_EVPN_RESPONSE = """
<evpn-ip-prefix-database-information>
</evpn-ip-prefix-database-information>
"""

MIXED_STATUS_RESPONSE = """
<evpn-ip-prefix-database-information>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Accepted</adv-ip-route-status>
        <ip-prefix>192.168.1.1/32</ip-prefix>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Rejected</adv-ip-route-status>
        <ip-prefix>192.168.1.2/32</ip-prefix>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Pending</adv-ip-route-status>
        <ip-prefix>192.168.1.3/32</ip-prefix>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Invalid</adv-ip-route-status>
        <ip-prefix>192.168.1.4/32</ip-prefix>
    </evpn-ip-prefix-database>
    <evpn-ip-prefix-database>
        <adv-ip-route-status>Unknown Status</adv-ip-route-status>
        <ip-prefix>192.168.1.5/32</ip-prefix>
    </evpn-ip-prefix-database>
</evpn-ip-prefix-database-information>
"""

def get_mock_xml_response(response_type: str):
    """Get parsed XML response for testing."""
    responses = {
        'healthy': HEALTHY_EVPN_RESPONSE,
        'rejected': REJECTED_ROUTES_RESPONSE,
        'empty': EMPTY_EVPN_RESPONSE,
        'mixed': MIXED_STATUS_RESPONSE
    }
    
    if response_type not in responses:
        raise ValueError(f"Unknown response type: {response_type}")
    
    return etree.fromstring(responses[response_type])

# Expected results for each scenario
EXPECTED_RESULTS = {
    'healthy': {
        'Accepted': 3,
        'Rejected': 0,
        'Pending': 0,
        'Invalid': 0,
        'Unknown': 0
    },
    'rejected': {
        'Accepted': 1,
        'Rejected': 2,
        'Pending': 1,
        'Invalid': 0,
        'Unknown': 0
    },
    'empty': {
        'Accepted': 0,
        'Rejected': 0,
        'Pending': 0,
        'Invalid': 0,
        'Unknown': 0
    },
    'mixed': {
        'Accepted': 1,
        'Rejected': 1,
        'Pending': 1,
        'Invalid': 1,
        'Unknown': 1
    }
}