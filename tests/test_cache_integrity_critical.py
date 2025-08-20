"""CRITICAL cache integrity tests - these should catch real bugs, not just adapt to broken behavior."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from scripts.calculate_skill_ratings import SkillRatingCalculator


class TestCacheIntegrityViolations:
    """Test that cache system maintains data integrity and doesn't use stale data."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)
    
    @pytest.fixture
    def calculator(self, temp_cache_dir):
        return SkillRatingCalculator(cache_dir=temp_cache_dir)
    
    def test_cache_key_mismatch_should_recalculate(self, calculator):
        """CRITICAL: Cache with different input data should NOT be used."""
        skill_id = "test_skill"
        
        # Original tournament data
        original_data = {
            "match_history": [
                {
                    "match_id": "match1",
                    "model_a": "model_a", 
                    "model_b": "model_b",
                    "winner": "A",
                    "timestamp": "2024-01-01T00:00:00"
                }
            ]
        }
        
        # Calculate with original data - this creates cache
        with patch.object(calculator, '_calculate_openskill_ratings') as mock_calculate:
            mock_calculate.return_value = {
                "model_ratings": {"model_a": {"mu": 1600, "sigma": 90}},
                "model_rankings": [{"model_id": "model_a", "rating": 1600}],
                "match_progression": []
            }
            
            original_cache_key = calculator._generate_cache_key(
                [{"id": "model_a"}, {"id": "model_b"}], 
                [{"id": "judge1"}], 
                [{"id": "eval1", "_metadata": {"skill": "test_skill"}}],
                {"test_skill": original_data}
            )
            
            result1 = calculator.calculate_skill_ratings(skill_id, original_data, original_cache_key)
            assert mock_calculate.call_count == 1  # Should calculate first time
        
        # Modified tournament data - different winner
        modified_data = {
            "match_history": [
                {
                    "match_id": "match1",
                    "model_a": "model_a",
                    "model_b": "model_b", 
                    "winner": "B",  # CHANGED - model_b wins now
                    "timestamp": "2024-01-01T00:00:00"
                }
            ]
        }
        
        # Calculate with modified data - should generate different cache key
        with patch.object(calculator, '_calculate_openskill_ratings') as mock_calculate2:
            mock_calculate2.return_value = {
                "model_ratings": {"model_b": {"mu": 1600, "sigma": 90}},
                "model_rankings": [{"model_id": "model_b", "rating": 1600}], 
                "match_progression": []
            }
            
            modified_cache_key = calculator._generate_cache_key(
                [{"id": "model_a"}, {"id": "model_b"}],
                [{"id": "judge1"}], 
                [{"id": "eval1", "_metadata": {"skill": "test_skill"}}],
                {"test_skill": modified_data}
            )
            
            # CRITICAL TEST: Cache keys should be different for different data
            assert original_cache_key != modified_cache_key, \
                "INTEGRITY VIOLATION: Different input data produced same cache key!"
            
            result2 = calculator.calculate_skill_ratings(skill_id, modified_data, modified_cache_key)
            assert mock_calculate2.call_count == 1  # Should calculate again, not use cache
            
            # Results should be different because data is different
            assert result1 != result2, \
                "INTEGRITY VIOLATION: Different input data produced same results!"
    
    def test_corrupted_cache_file_handling(self, calculator):
        """Test that corrupted cache files don't crash the system or return bad data."""
        skill_id = "test_skill"
        cache_key = "test_key"
        
        # Create corrupted cache file
        cache_path = calculator._get_cache_path(skill_id, cache_key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write invalid JSON
        with open(cache_path, 'w') as f:
            f.write("invalid json {corrupt")
        
        tournament_data = {
            "match_history": [
                {
                    "match_id": "match1",
                    "model_a": "model_a",
                    "model_b": "model_b", 
                    "winner": "A",
                    "timestamp": "2024-01-01T00:00:00"
                }
            ]
        }
        
        # Should handle corruption gracefully and recalculate
        with patch.object(calculator, '_calculate_openskill_ratings') as mock_calculate:
            mock_calculate.return_value = {
                "model_ratings": {"model_a": {"mu": 1600, "sigma": 90}},
                "model_rankings": [{"model_id": "model_a", "rating": 1600}],
                "match_progression": []
            }
            
            result = calculator.calculate_skill_ratings(skill_id, tournament_data, cache_key)
            
            # Should recalculate due to corrupted cache
            assert mock_calculate.call_count == 1
            assert result is not None
            
            # Corrupted cache file should be cleaned up
            assert not cache_path.exists() or cache_path.stat().st_size == 0
    
    def test_cache_filename_parsing_vulnerability(self, calculator):
        """Test that cache filename parsing can't be exploited."""
        # Create cache files with tricky names that could confuse parsing
        tricky_names = [
            "skill_with_many_underscores_in_name_cache123.json",
            "skill__double_underscore_cache456.json", 
            "no_underscore.json",
            "_starts_with_underscore_cache789.json",
            "ends_with_underscore__cache999.json"
        ]
        
        models = [{"id": "model1"}]
        judges = [{"id": "judge1"}] 
        evals = [{"id": "eval1", "_metadata": {"skill": "legitimate_skill"}}]
        
        for filename in tricky_names:
            cache_file = calculator.cache_dir / filename
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create cache with legitimate data
            cache_data = {
                "skill_id": "legitimate_skill",
                "model_ratings": {"model1": {"mu": 1500, "sigma": 100}},
                "total_matches": 1
            }
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
        
        # Cleanup should handle all files correctly without crashing
        with patch("builtins.print"):
            calculator.cleanup_invalid_rating_cache(models, judges, evals)
        
        # Should not crash and should handle edge cases appropriately
        # (exact behavior depends on parsing logic, but shouldn't crash)


class TestCacheConsistencyViolations:
    """Test cache consistency across different components."""
    
    def test_skill_rating_cache_vs_tournament_cache_consistency(self):
        """CRITICAL: Tournament cache and skill rating cache should be consistent."""
        # This is a critical test that our current implementation might fail
        # If tournament data changes, both caches should be invalidated together
        
        with tempfile.TemporaryDirectory() as temp_dir:
            calc = SkillRatingCalculator(cache_dir=Path(temp_dir))
            
            # Simulate scenario where tournament cache is updated but skill rating cache is stale
            skill_cache_file = calc._get_cache_path("test_skill", "old_cache_key")
            skill_cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create stale skill rating cache
            stale_data = {
                "skill_id": "test_skill",
                "model_ratings": {"old_model": {"mu": 1500, "sigma": 100}},
                "cache_key": "old_cache_key",
                "total_matches": 5
            }
            with open(skill_cache_file, 'w') as f:
                json.dump(stale_data, f)
            
            # New tournament data with different models
            new_tournament_data = {
                "match_history": [
                    {
                        "match_id": "new_match", 
                        "model_a": "new_model_a",
                        "model_b": "new_model_b",
                        "winner": "A",
                        "timestamp": "2024-01-02T00:00:00"
                    }
                ]
            }
            
            new_cache_key = calc._generate_cache_key(
                [{"id": "new_model_a"}, {"id": "new_model_b"}],
                [{"id": "judge1"}],
                [{"id": "eval1", "_metadata": {"skill": "test_skill"}}], 
                {"test_skill": new_tournament_data}
            )
            
            # CRITICAL: Should not use stale cache when cache key is different
            assert new_cache_key != "old_cache_key", \
                "Cache key generation failed - same key for different data!"
            
            with patch.object(calc, '_calculate_openskill_ratings') as mock_calc:
                mock_calc.return_value = {
                    "model_ratings": {"new_model_a": {"mu": 1600, "sigma": 90}},
                    "model_rankings": [{"model_id": "new_model_a", "rating": 1600}],
                    "match_progression": []
                }
                
                result = calc.calculate_skill_ratings("test_skill", new_tournament_data, new_cache_key)
                
                # Should recalculate because cache key is different
                assert mock_calc.call_count == 1, \
                    "INTEGRITY VIOLATION: Used stale cache with different cache key!"
                
                # Result should reflect new data
                assert "new_model_a" in result["model_ratings"], \
                    "Results don't match new tournament data!"
                assert "old_model" not in result["model_ratings"], \
                    "Results contain stale model data!"


class TestCacheSecurityViolations:
    """Test potential security issues in cache handling."""
    
    def test_cache_directory_traversal_prevention(self):
        """Test that cache paths can't escape intended directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            calc = SkillRatingCalculator(cache_dir=Path(temp_dir) / "safe_cache")
            
            # Try malicious skill IDs that attempt directory traversal
            malicious_skills = [
                "../../../etc/passwd",
                "..\\..\\windows\\system32",
                "skill/../../outside", 
                "skill\x00null_byte",
                "skill/../../../tmp/malicious"
            ]
            
            for malicious_skill in malicious_skills:
                cache_path = calc._get_cache_path(malicious_skill, "test_key")
                
                # CRITICAL: Cache path should be contained within cache directory
                try:
                    # Resolve to absolute path to check containment
                    resolved_cache = cache_path.resolve()
                    resolved_cache_dir = calc.cache_dir.resolve()
                    
                    # Ensure cache file is within intended directory
                    assert str(resolved_cache).startswith(str(resolved_cache_dir)), \
                        f"SECURITY VIOLATION: Cache path {resolved_cache} escapes cache directory {resolved_cache_dir}!"
                        
                except (OSError, ValueError) as e:
                    # Acceptable if OS rejects the malicious path
                    pass
    
    def test_cache_key_collision_resistance(self):
        """Test that similar inputs don't produce the same cache key."""
        with tempfile.TemporaryDirectory() as temp_dir:
            calc = SkillRatingCalculator(cache_dir=Path(temp_dir))
            
            models = [{"id": "model1"}, {"id": "model2"}]
            judges = [{"id": "judge1"}]
            evals = [{"id": "eval1", "_metadata": {"skill": "test_skill"}}]
            
            # Create similar but different tournament data
            data1 = {"test_skill": {"match_history": [
                {"match_id": "match1", "model_a": "model1", "model_b": "model2", "winner": "A"}
            ]}}
            
            data2 = {"test_skill": {"match_history": [
                {"match_id": "match1", "model_a": "model1", "model_b": "model2", "winner": "B"}  # Only winner different
            ]}}
            
            key1 = calc._generate_cache_key(models, judges, evals, data1)
            key2 = calc._generate_cache_key(models, judges, evals, data2)
            
            # CRITICAL: Different data should produce different cache keys
            assert key1 != key2, \
                f"INTEGRITY VIOLATION: Different tournament data produced same cache key! key1={key1}, key2={key2}"
            
            # Test more subtle differences
            data3 = {"test_skill": {"match_history": [
                {"match_id": "match1", "model_a": "model2", "model_b": "model1", "winner": "A"}  # Swapped models
            ]}}
            
            key3 = calc._generate_cache_key(models, judges, evals, data3)
            
            assert key1 != key3, \
                "INTEGRITY VIOLATION: Swapped model order produced same cache key!"
            assert key2 != key3, \
                "INTEGRITY VIOLATION: Different model arrangements produced same cache key!"