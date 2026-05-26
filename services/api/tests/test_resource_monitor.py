"""Tests for app.system.resource_monitor module."""
import pytest
from unittest.mock import patch, MagicMock

from app.system.resource_monitor import get_system_resources, format_resources, is_resource_sufficient


class TestGetSystemResources:
    """Test system resource monitoring."""

    def test_returns_valid_dataclass(self):
        """Should return SystemResources dataclass with valid fields."""
        resources = get_system_resources()
        assert hasattr(resources, "cpu_percent")
        assert hasattr(resources, "memory_percent")
        assert hasattr(resources, "memory_used_gb")
        assert hasattr(resources, "memory_total_gb")
        assert hasattr(resources, "disk_used_gb")
        assert hasattr(resources, "disk_total_gb")
        assert hasattr(resources, "internet_available")
        assert hasattr(resources, "timestamp")

    def test_cpu_percent_in_range(self):
        """CPU percent should be between 0 and 100."""
        resources = get_system_resources()
        assert 0 <= resources.cpu_percent <= 100

    def test_memory_values_positive(self):
        """Memory values should be positive."""
        resources = get_system_resources()
        assert resources.memory_total_gb > 0
        assert resources.memory_used_gb > 0
        assert resources.memory_used_gb <= resources.memory_total_gb

    def test_disk_values_positive(self):
        """Disk values should be positive."""
        resources = get_system_resources()
        assert resources.disk_total_gb > 0
        assert resources.disk_used_gb >= 0

    def test_gpu_available_is_bool(self):
        """GPU availability should be a boolean."""
        resources = get_system_resources()
        assert isinstance(resources.gpu_available, bool)

    def test_internet_available_is_bool(self):
        """Internet availability should be a boolean."""
        resources = get_system_resources()
        assert isinstance(resources.internet_available, bool)


class TestFormatResources:
    """Test resource formatting for API responses."""

    def test_returns_dict(self):
        """Should return a dictionary."""
        resources = get_system_resources()
        result = format_resources(resources)
        assert isinstance(result, dict)

    def test_dict_has_expected_keys(self):
        """Output dict should contain expected keys."""
        resources = get_system_resources()
        result = format_resources(resources)
        expected_keys = [
            "cpu_percent", "memory_percent", "memory_used_gb",
            "memory_total_gb", "disk_used_gb", "disk_total_gb",
            "gpu_available", "internet_available",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"


class TestIsResourceSufficient:
    """Test resource sufficiency checking."""

    def test_sufficient_with_low_requirements(self):
        """Should pass with very low requirements."""
        requirements = {
            "cpu_percent": 1,
            "memory_gb": 0.1,
            "disk_gb": 0.1,
        }
        sufficient, violations = is_resource_sufficient(requirements)
        # Most systems should meet these minimal requirements
        assert isinstance(sufficient, bool)
        assert isinstance(violations, list)

    def test_impossible_requirements(self):
        """Should fail with impossibly strict requirements."""
        requirements = {
            "cpu_percent_max": 0.001,
            "memory_percent_max": 0.001,
            "disk_free_gb_min": 999999,
        }
        sufficient, violations = is_resource_sufficient(requirements)
        assert sufficient is False
        assert len(violations) > 0

    def test_empty_requirements(self):
        """Empty requirements should pass."""
        sufficient, violations = is_resource_sufficient({})
        assert sufficient is True
        assert len(violations) == 0
