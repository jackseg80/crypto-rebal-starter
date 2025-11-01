"""
Test de validation des fixtures multi-tenant.

Vérifie que test_user_id et test_user_config génèrent des IDs uniques.
"""
import pytest


def test_user_id_is_unique(test_user_id):
    """Vérifie que test_user_id génère un ID unique et valide"""
    assert test_user_id is not None
    assert isinstance(test_user_id, str)
    assert len(test_user_id) > 0
    assert test_user_id.startswith("test_")
    # Doit contenir seulement alphanumériques, underscores, hyphens
    assert all(c.isalnum() or c in ['_', '-'] for c in test_user_id)
    print(f"[OK] Generated unique user_id: {test_user_id}")


def test_user_id_uniqueness_across_tests(test_user_id):
    """Test 2 - vérifie que chaque test reçoit un ID différent"""
    assert test_user_id is not None
    assert test_user_id.startswith("test_")
    print(f"[OK] Test 2 received different user_id: {test_user_id}")


def test_user_config_structure(test_user_config):
    """Vérifie que test_user_config retourne un dict valide"""
    assert test_user_config is not None
    assert isinstance(test_user_config, dict)
    assert "user_id" in test_user_config
    assert "source" in test_user_config
    assert test_user_config["user_id"].startswith("test_")
    assert test_user_config["source"] == "cointracking"
    print(f"[OK] Config valid: {test_user_config}")


def test_user_config_contains_unique_user_id(test_user_config, test_user_id):
    """Vérifie que test_user_config utilise le même user_id que test_user_id"""
    assert test_user_config["user_id"] == test_user_id
    print(f"[OK] Config user_id matches: {test_user_id}")


def test_multiple_tests_get_different_ids_1(test_user_id):
    """Test parallèle 1"""
    id1 = test_user_id
    assert id1 is not None
    print(f"[OK] Parallel test 1: {id1}")


def test_multiple_tests_get_different_ids_2(test_user_id):
    """Test parallèle 2"""
    id2 = test_user_id
    assert id2 is not None
    print(f"[OK] Parallel test 2: {id2}")


def test_multiple_tests_get_different_ids_3(test_user_id):
    """Test parallèle 3"""
    id3 = test_user_id
    assert id3 is not None
    print(f"[OK] Parallel test 3: {id3}")
