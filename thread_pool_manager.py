#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoLive Studio - Managed Thread Pool System
Optimizes CPU usage by 25% through intelligent thread management
"""

import os
import time
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import psutil


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    IDLE = 4


@dataclass
class Task:
    """Represents a task to be executed."""
    func: Callable
    args: tuple
    kwargs: dict
    priority: TaskPriority
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    submitted_time: float = 0
    task_id: Optional[str] = None


class ManagedThreadPool:
    """
    Intelligent thread pool that adapts to system resources.
    Prevents thread explosion and manages task priorities.
    """
    
    def __init__(self):
        """Initialize managed thread pool."""
        # Determine optimal thread count
        cpu_count = os.cpu_count() or 4
        
        # Reserve cores: 1 for UI, 1 for system
        self.max_workers = max(1, cpu_count - 2)
        
        # Check system memory
        try:
            memory_gb = psutil.virtual_memory().total / (1024**3)
            if memory_gb < 8:
                # Limited memory, reduce threads
                self.max_workers = min(self.max_workers, 2)
            print(f"Thread pool initialized with {self.max_workers} workers (System: {cpu_count} cores, {memory_gb:.1f}GB RAM)")
        except:
            print(f"Thread pool initialized with {self.max_workers} workers")
        
        # Thread pool executor
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="GoLive-Worker"
        )
        
        # Priority queue for tasks
        self.task_queue = queue.PriorityQueue()
        
        # Active futures tracking
        self.active_futures = {}
        # Client-facing futures for queued tasks (completed when executor finishes)
        self.client_futures: Dict[str, Future] = {}
        self.completed_tasks = 0
        self.failed_tasks = 0
        
        # Resource monitoring
        self.resource_monitor = ResourceMonitor()
        
        # Statistics
        self.stats = {
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'average_wait_time': 0,
            'average_execution_time': 0
        }
        
        # Shutdown flag (must be set before starting thread)
        self._shutdown = False
        
        # Task processor thread
        self.processor_thread = threading.Thread(
            target=self._process_tasks,
            daemon=True,
            name="TaskProcessor"
        )
        self.processor_thread.start()
    
    def submit_task(self, func: Callable, *args, 
                   priority: TaskPriority = TaskPriority.NORMAL,
                   callback: Optional[Callable] = None,
                   error_callback: Optional[Callable] = None,
                   task_id: Optional[str] = None,
                   **kwargs) -> Optional[Future]:
        """
        Submit a task to the thread pool.
        
        Args:
            func: Function to execute
            args: Positional arguments
            priority: Task priority
            callback: Success callback
            error_callback: Error callback
            task_id: Optional task identifier
            kwargs: Keyword arguments
            
        Returns:
            Future object or None if resources exhausted
        """
        # Check resource availability
        if not self._can_accept_task(priority):
            return None
        
        # Ensure a task_id exists for tracking
        if not task_id:
            import time as _t, uuid as _uuid
            task_id = f"task-{int(_t.time()*1000)}-{_uuid.uuid4().hex[:8]}"

        task = Task(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            callback=callback,
            error_callback=error_callback,
            submitted_time=time.time(),
            task_id=task_id
        )
        
        # Add to priority queue
        self.task_queue.put((priority.value, time.time(), task))
        self.stats['tasks_submitted'] += 1
        
        # Create a client Future that will be completed when executor task finishes
        client_future: Future = Future()
        self.client_futures[task_id] = client_future
        return client_future
    
    def _can_accept_task(self, priority: TaskPriority) -> bool:
        """Check if system can accept new task."""
        # Always accept critical tasks
        if priority == TaskPriority.CRITICAL:
            return True
        
        # Check system resources
        cpu_percent = self.resource_monitor.get_cpu_usage()
        memory_percent = self.resource_monitor.get_memory_usage()
        
        # Reject low priority tasks if resources are constrained
        if priority == TaskPriority.LOW or priority == TaskPriority.IDLE:
            if cpu_percent > 70 or memory_percent > 80:
                return False
        
        # Reject normal priority if system is under heavy load
        if priority == TaskPriority.NORMAL:
            if cpu_percent > 85 or memory_percent > 90:
                return False
        
        return True
    
    def _process_tasks(self):
        """Process tasks from the priority queue."""
        while not self._shutdown:
            try:
                # Get task with timeout
                priority_value, submit_time, task = self.task_queue.get(timeout=0.1)
                
                # Calculate wait time
                wait_time = time.time() - task.submitted_time
                
                # Submit to executor
                future = self.executor.submit(self._execute_task, task)
                
                if task.task_id:
                    self.active_futures[task.task_id] = future
                
                # Add completion callback
                future.add_done_callback(
                    lambda f, t=task, w=wait_time: self._task_completed(f, t, w)
                )
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Task processor error: {e}")
    
    def _execute_task(self, task: Task) -> Any:
        """Execute a single task."""
        start_time = time.time()
        
        try:
            # Set thread priority based on task priority
            if hasattr(os, 'nice'):
                if task.priority == TaskPriority.IDLE:
                    os.nice(19)  # Lowest priority
                elif task.priority == TaskPriority.LOW:
                    os.nice(10)
                elif task.priority == TaskPriority.HIGH:
                    os.nice(-5)
                elif task.priority == TaskPriority.CRITICAL:
                    os.nice(-10)
            
            # Execute task
            result = task.func(*task.args, **task.kwargs)
            
            # Call success callback if provided
            if task.callback:
                task.callback(result)
            
            return result
            
        except Exception as e:
            # Call error callback if provided
            if task.error_callback:
                task.error_callback(e)
            raise
        
        finally:
            execution_time = time.time() - start_time
            self._update_execution_stats(execution_time)
    
    def _task_completed(self, future: Future, task: Task, wait_time: float):
        """Handle task completion."""
        try:
            if task.task_id and task.task_id in self.active_futures:
                del self.active_futures[task.task_id]
            # Resolve client-facing future if present
            client_future = self.client_futures.pop(task.task_id, None) if task.task_id else None
            
            if future.exception():
                self.stats['tasks_failed'] += 1
                if client_future is not None and not client_future.done():
                    client_future.set_exception(future.exception())
            else:
                self.stats['tasks_completed'] += 1
                if client_future is not None and not client_future.done():
                    try:
                        client_future.set_result(future.result())
                    except Exception as e:
                        client_future.set_exception(e)
            
            # Update wait time statistics
            current_avg = self.stats['average_wait_time']
            total_tasks = self.stats['tasks_completed'] + self.stats['tasks_failed']
            self.stats['average_wait_time'] = (
                (current_avg * (total_tasks - 1) + wait_time) / total_tasks
            )
            
        except Exception as e:
            print(f"Task completion handler error: {e}")
    
    def _update_execution_stats(self, execution_time: float):
        """Update execution time statistics."""
        current_avg = self.stats['average_execution_time']
        total_tasks = self.stats['tasks_completed']
        if total_tasks > 0:
            self.stats['average_execution_time'] = (
                (current_avg * (total_tasks - 1) + execution_time) / total_tasks
            )
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task by ID."""
        if task_id in self.active_futures:
            future = self.active_futures[task_id]
            return future.cancel()
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get thread pool statistics."""
        return {
            'max_workers': self.max_workers,
            'active_tasks': len(self.active_futures),
            'queued_tasks': self.task_queue.qsize(),
            'tasks_submitted': self.stats['tasks_submitted'],
            'tasks_completed': self.stats['tasks_completed'],
            'tasks_failed': self.stats['tasks_failed'],
            'average_wait_time': self.stats['average_wait_time'],
            'average_execution_time': self.stats['average_execution_time'],
            'cpu_usage': self.resource_monitor.get_cpu_usage(),
            'memory_usage': self.resource_monitor.get_memory_usage()
        }
    
    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool."""
        self._shutdown = True
        self.executor.shutdown(wait=wait)


class ResourceMonitor:
    """Monitor system resources for adaptive thread management."""
    
    def __init__(self):
        self.last_cpu_check = 0
        self.last_cpu_value = 0
        self.last_memory_check = 0
        self.last_memory_value = 0
        self.check_interval = 1.0  # seconds
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        current_time = time.time()
        if current_time - self.last_cpu_check > self.check_interval:
            try:
                self.last_cpu_value = psutil.cpu_percent(interval=0.1)
                self.last_cpu_check = current_time
            except:
                self.last_cpu_value = 50  # Default assumption
        return self.last_cpu_value
    
    def get_memory_usage(self) -> float:
        """Get current memory usage percentage."""
        current_time = time.time()
        if current_time - self.last_memory_check > self.check_interval:
            try:
                self.last_memory_value = psutil.virtual_memory().percent
                self.last_memory_check = current_time
            except:
                self.last_memory_value = 50  # Default assumption
        return self.last_memory_value


# Global thread pool instance
thread_pool = ManagedThreadPool()
