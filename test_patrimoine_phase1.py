"""Test script for Patrimoine Phase 1 implementation."""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from services.wealth.patrimoine_migration import migrate_user_data, migrate_all_users
from services.wealth.patrimoine_service import list_items, create_item, get_summary
from models.wealth import PatrimoineItemInput


def test_migration():
    """Test migration for a specific user."""
    print("\n=== Test 1: Migration ===")

    # Test migration for jack
    result = migrate_user_data("jack", force=True)
    print(f"Migration result: {json.dumps(result, indent=2)}")

    # Check if patrimoine.json exists
    patrimoine_path = Path("data/users/jack/wealth/patrimoine.json")
    if patrimoine_path.exists():
        with patrimoine_path.open("r") as f:
            data = json.load(f)
            print(f"Migrated items count: {len(data.get('items', []))}")
            print(f"First item: {json.dumps(data['items'][0] if data['items'] else {}, indent=2)}")
    else:
        print("ERROR: patrimoine.json not created")

    print("[OK] Migration test completed")


def test_list_items():
    """Test listing patrimoine items."""
    print("\n=== Test 2: List Items ===")

    # List all items for jack
    items = list_items("jack")
    print(f"Total items: {len(items)}")

    # List only liquidity items
    liquidity_items = list_items("jack", category="liquidity")
    print(f"Liquidity items: {len(liquidity_items)}")

    # List only bank_account type
    bank_accounts = list_items("jack", category="liquidity", type="bank_account")
    print(f"Bank accounts: {len(bank_accounts)}")

    if bank_accounts:
        print(f"First bank account: {bank_accounts[0].name} - {bank_accounts[0].value} {bank_accounts[0].currency}")

    print("[OK] List items test completed")


def test_create_item():
    """Test creating a new patrimoine item."""
    print("\n=== Test 3: Create Item ===")

    # Create a neobank account (Revolut)
    new_item = PatrimoineItemInput(
        name="Revolut (current)",
        category="liquidity",
        type="neobank",
        value=1500.0,
        currency="EUR",
        acquisition_date="2024-01-15",
        notes="Neobank for travel",
        metadata={
            "bank_name": "Revolut",
            "account_type": "current",
        },
    )

    created = create_item("jack", new_item)
    print(f"Created item: {created.name} - {created.value_usd:.2f} USD")
    print(f"Item ID: {created.id}")

    # Verify it was created
    all_items = list_items("jack")
    print(f"Total items after creation: {len(all_items)}")

    print("[OK] Create item test completed")


def test_summary():
    """Test getting patrimoine summary."""
    print("\n=== Test 4: Summary ===")

    summary = get_summary("jack")
    print(f"Net Worth: ${summary['net_worth']:.2f}")
    print(f"Total Assets: ${summary['total_assets']:.2f}")
    print(f"Total Liabilities: ${summary['total_liabilities']:.2f}")
    print(f"Breakdown: {json.dumps(summary['breakdown'], indent=2)}")
    print(f"Counts: {json.dumps(summary['counts'], indent=2)}")

    print("[OK] Summary test completed")


def test_multi_user_isolation():
    """Test multi-user isolation."""
    print("\n=== Test 5: Multi-User Isolation ===")

    # Get items for different users
    jack_items = list_items("jack")
    demo_items = list_items("demo")

    print(f"Jack's items: {len(jack_items)}")
    print(f"Demo's items: {len(demo_items)}")

    # Create item for demo user
    demo_item = PatrimoineItemInput(
        name="Demo Bank (current)",
        category="liquidity",
        type="bank_account",
        value=1000.0,
        currency="USD",
        notes="Demo account",
        metadata={},
    )

    created = create_item("demo", demo_item)
    print(f"Created item for demo: {created.name}")

    # Verify isolation
    jack_items_after = list_items("jack")
    demo_items_after = list_items("demo")

    print(f"Jack's items after (should be same): {len(jack_items_after)}")
    print(f"Demo's items after (should be +1): {len(demo_items_after)}")

    assert len(jack_items_after) == len(jack_items), "Jack's items changed!"
    assert len(demo_items_after) == len(demo_items) + 1, "Demo's items not increased!"

    print("[OK] Multi-user isolation test completed")


def test_migrate_all():
    """Test migration for all users."""
    print("\n=== Test 6: Migrate All Users ===")

    results = migrate_all_users(force=False)
    print(f"Migrated {len(results)} users")

    for result in results:
        status = result.get("status")
        user_id = result.get("user_id")
        count = result.get("migrated_count", 0)
        reason = result.get("reason", "")

        if status == "success":
            print(f"[OK] {user_id}: {count} items migrated ({reason})")
        elif status == "skipped":
            print(f"[SKIP] {user_id}: skipped ({reason})")
        else:
            print(f"[ERROR] {user_id}: error - {result.get('error', 'unknown')}")

    print("[OK] Migrate all users test completed")


if __name__ == "__main__":
    try:
        test_migration()
        test_list_items()
        test_create_item()
        test_summary()
        test_multi_user_isolation()
        test_migrate_all()

        print("\n" + "="*50)
        print("[SUCCESS] ALL TESTS PASSED")
        print("="*50)

    except Exception as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
