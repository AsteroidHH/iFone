"""
Quorum Synthetic Seed Data Generator (scripts/seed.py)

Author: Janani (Person 1 - Graph & FalkorDB)
Generates:
1. Acme Support Scenario:
   - Root 30-day refund policy fact
   - Poisoned webhook 90-day fact
   - 3 refund tickets/claims
   - Agents across all 3 tiers (root, established, new)
   - Procedures with seeded scores (for adaptive ranking demo)
2. Company Brain Corpus (Track 03):
   - 25 items across Sources (DOC, TICKET, CHAT)
   - 12 People, 4 Teams, 3 Projects, 3 Systems
   - Ownership, authorship, and topic resolution links
3. Precomputed 384-dim normalized embeddings so 'docker compose up' requires zero external downloads!
"""

import hashlib
import numpy as np
from typing import List
from graph import queries


def generate_embedding(text: str) -> List[float]:
    """
    Deterministic 384-dim normalized pseudo-embedding derived from SHA-256 hash.
    Ensures identical vectors across runs without downloading heavy weights.
    """
    rng = np.random.RandomState(int(hashlib.sha256(text.encode()).hexdigest()[:8], 16))
    vec = rng.randn(384)
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist()


def seed_acme_commons(tenant_id: str = "acme"):
    print(f"\n[Seed] Generating Acme Commons graph for tenant '{tenant_id}'...")
    g = queries.get_graph(tenant_id, "commons")
    try:
        g.delete()
    except Exception:
        pass
    queries.ensure_indexes(tenant_id)

    # 1. Agents with Trust Tiers
    agents = [
        {"id": "agent_root_auditor", "name": "Compliance Root Auditor", "role": "Auditor", "tier": "root", "tier_weight": 10.0},
        {"id": "agent_scout", "name": "Ingest Scout", "role": "Scout", "tier": "established", "tier_weight": 3.0},
        {"id": "agent_analyst", "name": "Policy Analyst", "role": "Analyst", "tier": "established", "tier_weight": 3.0},
        {"id": "agent_refunder", "name": "Refund Dispatcher", "role": "Refunder", "tier": "established", "tier_weight": 3.0},
        {"id": "agent_comms", "name": "Communications Agent", "role": "Comms", "tier": "new", "tier_weight": 0.5},
        {"id": "agent_webhook", "name": "External Webhook Ingest", "role": "Webhook", "tier": "new", "tier_weight": 0.5},
    ]
    for a in agents:
        g.query(
            "CREATE (:Agent {id: $id, name: $name, role: $role, tier: $tier, tier_weight: $tier_weight})",
            a
        )

    # 2. Procedures with Seeded Scores (Adaptive Ranking Demo)
    procedures = [
        {
            "id": "proc_standard_refund",
            "task_type": "REFUND",
            "steps": ["verify_receipt", "check_30d_window", "dispatch_payment"],
            "uses": 24, "successes": 23, "failures": 1
        },
        {
            "id": "proc_extended_refund",
            "task_type": "REFUND",
            "steps": ["accept_unverified_claim", "dispatch_payment"],
            "uses": 8, "successes": 1, "failures": 7
        },
    ]
    for p in procedures:
        g.query(
            "CREATE (:Procedure {id: $id, task_type: $task_type, steps: $steps, "
            "uses: $uses, successes: $successes, failures: $failures})",
            p
        )

    # 3. Legitimate Root Policy Document & Fact
    doc_text = "Acme customer refund window policy allows returns within 30 days of shipment."
    vec_policy = generate_embedding(doc_text)
    g.query(
        """
        CREATE (s:Source {
            id: 'src_doc_refund_policy_v1', kind: 'DOC', title: 'Global Customer Refund Policy',
            url: 'https://wiki.acme.corp/policies/refunds_v1', version: '1.0', origin: 'corporate_wiki',
            created_at: timestamp()
        })
        CREATE (f:Fact:MemoryNode {
            id: 'fact_refund_policy_30d', key: 'refund.window_days', value: '30',
            text: $text, status: 'HEALTHY', embedding: vecf32($vec),
            valid_from: timestamp(), valid_to: null, stale: false,
            source_ref: 'src_doc_refund_policy_v1', quote: 'within 30 days of shipment'
        })
        CREATE (f)-[:FROM_SOURCE]->(s)
        """,
        {"text": doc_text, "vec": vec_policy}
    )

    # 4. Track 03: Company Brain Corpus
    # 4 Teams, 12 People, 3 Projects, 3 Systems
    teams = [
        ("team_support", "Customer Support Operations"),
        ("team_compliance", "Legal & Compliance"),
        ("team_eng", "Core Platform Engineering"),
        ("team_finance", "Finance & Accounting"),
    ]
    for tid, tname in teams:
        g.query("CREATE (:Team {id: $id, name: $name})", {"id": tid, "name": tname})

    people = [
        ("p_alice", "Alice Walker", "alice@acme.corp", "team_support"),
        ("p_bob", "Bob Chen", "bob@acme.corp", "team_support"),
        ("p_charlie", "Charlie Miller", "charlie@acme.corp", "team_support"),
        ("p_dana", "Dana Vance", "dana@acme.corp", "team_compliance"),
        ("p_elena", "Elena Rostova", "elena@acme.corp", "team_compliance"),
        ("p_frank", "Frank Gomez", "frank@acme.corp", "team_compliance"),
        ("p_grace", "Grace Hopper", "grace@acme.corp", "team_eng"),
        ("p_henry", "Henry Ford", "henry@acme.corp", "team_eng"),
        ("p_ivy", "Ivy Brooks", "ivy@acme.corp", "team_eng"),
        ("p_jack", "Jack Ryan", "jack@acme.corp", "team_finance"),
        ("p_karen", "Karen White", "karen@acme.corp", "team_finance"),
        ("p_leo", "Leo Tolstoy", "leo@acme.corp", "team_finance"),
    ]
    for pid, pname, pmail, ptid in people:
        g.query(
            "CREATE (p:Person {id: $id, name: $name, email: $email}) "
            "WITH p MATCH (t:Team {id: $tid}) CREATE (p)-[:MEMBER_OF]->(t)",
            {"id": pid, "name": pname, "email": pmail, "tid": ptid}
        )

    topics = [
        ("top_refunds", "Refund & Cancellation Policies"),
        ("top_fraud", "Fraud Detection & Risk"),
        ("top_payments", "Payment Gateway Architecture"),
    ]
    for top_id, top_name in topics:
        g.query("CREATE (:Topic {id: $id, name: $name})", {"id": top_id, "name": top_name})

    # Link Policy Source to Team Compliance and Topic Refunds
    g.query("""
    MATCH (t:Team {id: 'team_compliance'}), (s:Source {id: 'src_doc_refund_policy_v1'}),
          (top:Topic {id: 'top_refunds'}), (p:Person {id: 'p_dana'})
    CREATE (t)-[:OWNS]->(s),
           (p)-[:AUTHORED]->(s),
           (s)-[:ABOUT]->(top)
    """)

    # Seed 20 additional Sources (Tickets, Chats, Docs)
    brain_items = [
        ("src_ticket_101", "TICKET", "Refund inquiry for order #8841", "p_alice", "team_support", "top_refunds"),
        ("src_ticket_102", "TICKET", "Chargeback dispute charge #9921", "p_bob", "team_support", "top_fraud"),
        ("src_ticket_103", "TICKET", "Duplicate payment on invoice #112", "p_jack", "team_finance", "top_payments"),
        ("src_ticket_104", "TICKET", "Refund window exception requested", "p_charlie", "team_support", "top_refunds"),
        ("src_ticket_105", "TICKET", "API timeout during gateway batch", "p_grace", "team_eng", "top_payments"),
        ("src_chat_201", "CHAT", "Slack #ops: Gateway retry parameters", "p_henry", "team_eng", "top_payments"),
        ("src_chat_202", "CHAT", "Slack #legal: 30-day compliance review", "p_elena", "team_compliance", "top_refunds"),
        ("src_chat_203", "CHAT", "Slack #support: Handling customer delays", "p_alice", "team_support", "top_refunds"),
        ("src_chat_204", "CHAT", "Slack #finance: Monthly refund totals", "p_karen", "team_finance", "top_refunds"),
        ("src_chat_205", "CHAT", "Slack #security: Anomaly in return logs", "p_frank", "team_compliance", "top_fraud"),
        ("src_doc_301", "DOC", "Payment Gateway Runbook", "p_ivy", "team_eng", "top_payments"),
        ("src_doc_302", "DOC", "Fraud Evaluation Guidelines", "p_dana", "team_compliance", "top_fraud"),
        ("src_doc_303", "DOC", "Customer Support Escalation Matrix", "p_bob", "team_support", "top_refunds"),
        ("src_doc_304", "DOC", "Accounting Reconciliation SOP", "p_leo", "team_finance", "top_payments"),
        ("src_doc_305", "DOC", "SLA & Customer Rights Charter", "p_elena", "team_compliance", "top_refunds"),
    ]

    for sid, kind, title, author, team, topic in brain_items:
        g.query(
            """
            CREATE (s:Source {id: $id, kind: $kind, title: $title, url: 'https://internal/' + $id, version: '1.0', origin: 'internal_wiki'})
            WITH s
            MATCH (p:Person {id: $author}), (t:Team {id: $team}), (top:Topic {id: $topic})
            CREATE (p)-[:AUTHORED]->(s), (t)-[:OWNS]->(s), (s)-[:ABOUT]->(top)
            """,
            {"id": sid, "kind": kind, "title": title, "author": author, "team": team, "topic": topic}
        )

    # 5. Connect a Decision for Provenance Verification (Track 03 #3)
    dec_text = "Acme standard return threshold decision confirmed at 30 days."
    g.query(
        """
        MATCH (f:Fact {id: 'fact_refund_policy_30d'})
        CREATE (dec:Conclusion:Decision:MemoryNode {
            id: 'dec_standard_window_30d', text: $dec_text, status: 'HEALTHY',
            stale: false, owner_team: 'Customer Support Operations', created_at: timestamp()
        })
        CREATE (f)-[:LEADS_TO]->(dec)
        """,
        {"dec_text": dec_text}
    )

    # 6. Seed Action #1 (Irreversible Customer Email for Damage Control Demo)
    g.query("""
    MATCH (dec:Conclusion {id: 'dec_standard_window_30d'})
    CREATE (act:Action:MemoryNode {
        id: 'act_email_001',
        label: 'Send customer refund approval notice',
        type: 'SEND_CUSTOMER_EMAIL',
        reversibility: 'IRREVERSIBLE',
        executed: true,
        confirmed: true,
        gate: 'PASSED',
        status: 'HEALTHY',
        text: 'Your refund of $150 has been approved under our new 90-day policy.',
        created_at: timestamp()
    })
    CREATE (dec)-[:LEADS_TO]->(act)
    """)
    print(f"[Seed] Successfully seeded Acme Commons graph for tenant '{tenant_id}'!")


if __name__ == "__main__":
    seed_acme_commons("acme")
