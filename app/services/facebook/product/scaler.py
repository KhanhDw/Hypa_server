import time
import asyncio
from typing import Dict, List, Optional, Callable
from collections import deque, defaultdict
import statistics

from .metrics import FACEBOOK_QUEUE_WAITING_DURATION


class WorkerScaler:
    """
    Enhanced auto-scaling system with:
    1. Queue length-based scaling
    2. Per-mode queue scaling
    3. Memory-based worker management
    4. Hysteresis to prevent oscillation
    """
    
    def __init__(self, 
                 min_workers: int = 1,
                 max_workers: int = 10,
                 scale_up_threshold: float = 1.0,    # P90 queue wait time in seconds to trigger scale up
                 scale_down_threshold: float = 0.2,  # P90 queue wait time in seconds to trigger scale down
                 queue_length_scale_up: int = 10,    # Queue length to trigger scale up
                 queue_length_scale_down: int = 3,   # Queue length to trigger scale down
                 scaling_window: int = 50,           # Number of recent queue wait times to consider
                 cooldown_period: int = 30,          # Cooldown period in seconds between scaling actions
                 memory_threshold: float = 800.0):   # Memory threshold in MB to trigger worker restart
        
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.queue_length_scale_up = queue_length_scale_up
        self.queue_length_scale_down = queue_length_scale_down
        self.scaling_window = scaling_window
        self.cooldown_period = cooldown_period
        self.memory_threshold = memory_threshold
        
        # Track queue wait times (now by mode)
        self.queue_wait_times = defaultdict(lambda: deque(maxlen=scaling_window))
        
        # Track queue lengths by mode
        self.queue_lengths = defaultdict(int)
        
        # Track memory usage
        self.memory_usage = defaultdict(float)
        
        # Current worker count
        self.current_workers = min_workers
        
        # Scaling state
        self.last_scaling_action = time.time() - cooldown_period  # Allow immediate scaling initially
        self.scaling_history = deque(maxlen=100)
        
        # Hysteresis state
        self.is_scaling_up_mode = False
        self.is_scaling_down_mode = False
        
        # Memory management
        self.last_worker_restart = time.time()
        self.worker_restart_threshold = 300  # 5 minutes between restarts
        
    def add_queue_wait_time(self, wait_time: float, mode: str = "simple") -> None:
        """
        Add a queue wait time measurement
        """
        self.queue_wait_times[mode].append((time.time(), wait_time, mode))
        
    def update_queue_length(self, length: int, mode: str = "simple") -> None:
        """
        Update queue length for a specific mode
        """
        self.queue_lengths[mode] = length
        
    def update_memory_usage(self, memory_mb: float, worker_id: str = "default") -> None:
        """
        Update memory usage for a specific worker
        """
        self.memory_usage[worker_id] = memory_mb
        
    def should_scale_up_by_wait_time(self) -> bool:
        """
        Check if we should scale up based on P90 queue wait time
        """
        # Combine wait times from all modes
        all_wait_times = []
        for mode_wait_times in self.queue_wait_times.values():
            all_wait_times.extend([wait_time for _, wait_time, _ in list(mode_wait_times)[-self.scaling_window:]])
        
        if len(all_wait_times) < 10:  # Need minimum data points
            return False
        
        # Calculate P90
        p90_wait = self._calculate_percentile(all_wait_times, 90)
        
        # Apply hysteresis logic
        if p90_wait > self.scale_up_threshold:
            self.is_scaling_up_mode = True
            self.is_scaling_down_mode = False
            return True
        elif p90_wait < self.scale_down_threshold:
            self.is_scaling_up_mode = False
        
        return False
    
    def should_scale_up_by_length(self) -> bool:
        """
        Check if we should scale up based on queue length
        """
        total_queue_length = sum(self.queue_lengths.values())
        return total_queue_length >= self.queue_length_scale_up
    
    def should_scale_up(self) -> bool:
        """
        Check if we should scale up based on wait time OR queue length
        """
        return self.should_scale_up_by_wait_time() or self.should_scale_up_by_length()
    
    def should_scale_down_by_wait_time(self) -> bool:
        """
        Check if we should scale down based on P90 queue wait time
        """
        # Combine wait times from all modes
        all_wait_times = []
        for mode_wait_times in self.queue_wait_times.values():
            all_wait_times.extend([wait_time for _, wait_time, _ in list(mode_wait_times)[-self.scaling_window:]])
        
        if len(all_wait_times) < 10:  # Need minimum data points
            return False
        
        # Calculate P90
        p90_wait = self._calculate_percentile(all_wait_times, 90)
        
        # Apply hysteresis logic
        if p90_wait < self.scale_down_threshold:
            self.is_scaling_down_mode = True
            # Only scale down if we're not in scaling up mode or if wait time is significantly low
            return self.current_workers > self.min_workers and not self.is_scaling_up_mode
        elif p90_wait > self.scale_up_threshold:
            # Exit scaling down mode if wait times are high
            self.is_scaling_down_mode = False
        
        return False
    
    def should_scale_down_by_length(self) -> bool:
        """
        Check if we should scale down based on queue length
        """
        total_queue_length = sum(self.queue_lengths.values())
        return total_queue_length <= self.queue_length_scale_down
    
    def should_scale_down(self) -> bool:
        """
        Check if we should scale down based on wait time OR queue length
        """
        return self.should_scale_down_by_wait_time() and self.should_scale_down_by_length()
    
    def should_restart_workers(self) -> bool:
        """
        Check if memory usage is high enough to warrant worker restart
        """
        if time.time() - self.last_worker_restart < self.worker_restart_threshold:
            return False  # Respect restart cooldown
        
        # Check if any worker is using too much memory
        for worker_id, memory_mb in self.memory_usage.items():
            if memory_mb > self.memory_threshold:
                return True
        return False
    
    def can_scale_now(self) -> bool:
        """
        Check if we're past the cooldown period since the last scaling action
        """
        return time.time() - self.last_scaling_action > self.cooldown_period
    
    def scale_up(self) -> bool:
        """
        Scale up workers if conditions are met
        """
        if (self.current_workers < self.max_workers and 
            self.should_scale_up() and 
            self.can_scale_now()):
            
            self.current_workers += 1
            self.last_scaling_action = time.time()
            
            # Record scaling event
            self.scaling_history.append({
                'timestamp': time.time(),
                'action': 'scale_up',
                'from_workers': self.current_workers - 1,
                'to_workers': self.current_workers,
                'reason': 'high_queue_wait_time_or_length',
                'queue_lengths': dict(self.queue_lengths),
                'total_queue_length': sum(self.queue_lengths.values())
            })
            
            return True
        return False
    
    def scale_down(self) -> bool:
        """
        Scale down workers if conditions are met
        """
        if (self.current_workers > self.min_workers and 
            self.should_scale_down() and 
            self.can_scale_now()):
            
            self.current_workers -= 1
            self.last_scaling_action = time.time()
            
            # Record scaling event
            self.scaling_history.append({
                'timestamp': time.time(),
                'action': 'scale_down',
                'from_workers': self.current_workers + 1,
                'to_workers': self.current_workers,
                'reason': 'low_queue_wait_time_and_length',
                'queue_lengths': dict(self.queue_lengths),
                'total_queue_length': sum(self.queue_lengths.values())
            })
            
            return True
        return False
    
    def restart_workers_if_needed(self) -> bool:
        """
        Restart workers if memory usage is too high
        """
        if self.should_restart_workers():
            # This would trigger a worker restart process
            self.last_worker_restart = time.time()
            
            # Record restart event
            self.scaling_history.append({
                'timestamp': time.time(),
                'action': 'worker_restart',
                'reason': 'high_memory_usage',
                'memory_usage': dict(self.memory_usage),
                'high_memory_workers': [worker_id for worker_id, memory in self.memory_usage.items() 
                                        if memory > self.memory_threshold]
            })
            
            return True
        return False
    
    def get_workers_to_restart(self) -> List[str]:
        """
        Get list of workers that should be restarted due to high memory
        """
        return [worker_id for worker_id, memory in self.memory_usage.items() 
                if memory > self.memory_threshold]
    
    def get_suggested_worker_count(self) -> int:
        """
        Get the suggested worker count based on current metrics
        """
        all_wait_times = []
        for mode_wait_times in self.queue_wait_times.values():
            all_wait_times.extend([wait_time for _, wait_time, _ in list(mode_wait_times)[-self.scaling_window:]])
        
        if not all_wait_times:
            return self.current_workers
        
        p90_wait = self._calculate_percentile(all_wait_times, 90)
        total_queue_length = sum(self.queue_lengths.values())
        
        # Determine scaling factor based on both wait time and queue length
        scale_factor = 1.0
        
        if p90_wait > self.scale_up_threshold or total_queue_length >= self.queue_length_scale_up:
            # Need to scale up
            scale_factor = 1.2
        elif p90_wait < self.scale_down_threshold and total_queue_length <= self.queue_length_scale_down:
            # Can scale down
            scale_factor = 0.8
        
        suggested = int(self.current_workers * scale_factor)
        suggested = max(self.min_workers, min(self.max_workers, suggested))
        
        return suggested
    
    def get_current_status(self) -> Dict:
        """
        Get current scaling status
        """
        all_wait_times = []
        for mode_wait_times in self.queue_wait_times.values():
            all_wait_times.extend([wait_time for _, wait_time, _ in list(mode_wait_times)[-self.scaling_window:]])
        
        if all_wait_times:
            p90_wait = self._calculate_percentile(all_wait_times, 90)
            p50_wait = self._calculate_percentile(all_wait_times, 50)
        else:
            p90_wait = 0
            p50_wait = 0
        
        total_queue_length = sum(self.queue_lengths.values())
        
        return {
            'current_workers': self.current_workers,
            'suggested_workers': self.get_suggested_worker_count(),
            'p90_queue_wait_time': p90_wait,
            'p50_queue_wait_time': p50_wait,
            'total_queue_length': total_queue_length,
            'queue_lengths_by_mode': dict(self.queue_lengths),
            'should_scale_up': self.should_scale_up(),
            'should_scale_down': self.should_scale_down(),
            'should_restart_workers': self.should_restart_workers(),
            'can_scale_now': self.can_scale_now(),
            'is_scaling_up_mode': self.is_scaling_up_mode,
            'is_scaling_down_mode': self.is_scaling_down_mode,
            'last_scaling_action': self.last_scaling_action,
            'last_worker_restart': self.last_worker_restart,
            'cooldown_remaining': max(0, self.cooldown_period - (time.time() - self.last_scaling_action)),
            'memory_usage': dict(self.memory_usage),
            'high_memory_workers': [worker_id for worker_id, memory in self.memory_usage.items() 
                                    if memory > self.memory_threshold]
        }
    
    def _calculate_percentile(self, data: List[float], percentile: float) -> float:
        """
        Calculate percentile of a data list
        """
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_data) - 1)
        
        if lower_index == upper_index:
            return sorted_data[lower_index]
        
        # Interpolate between the two values
        fraction = index - lower_index
        return sorted_data[lower_index] + fraction * (sorted_data[upper_index] - sorted_data[lower_index])


# Global instance for use in other modules
scaler = WorkerScaler()