#!/usr/bin/env python3
"""
Script to check Habitica daily tasks status using habitipy
"""
import sys
from datetime import datetime
from habitipy import Habitipy, load_conf, DEFAULT_CONF
from habitipy.util import prettify

def check_daily_tasks(verbose=True):
    """
    Check status of Habitica daily tasks
    
    Args:
        verbose (bool): Whether to print detailed task information
        
    Returns:
        tuple: (incomplete_tasks, completed_tasks) lists
    """
    # Load configuration and create API client
    try:
        conf = load_conf(DEFAULT_CONF)
        api = Habitipy(conf)
    except Exception as e:
        print(f"Failed to initialize Habitica client: {e}")
        sys.exit(1)

    # Get all tasks
    try:
        tasks = api.tasks.user.get(type='dailys')
    except Exception as e:
        print(f"Failed to fetch tasks: {e}")
        sys.exit(1)

    # Filter for active dailies due today
    incomplete = []
    completed = []
    
    for task in tasks:
        if task.get('isDue', False):  # Only check tasks due today
            if task.get('completed', False):
                completed.append(task)
            else:
                incomplete.append(task)

    # Print status report if verbose
    if verbose:
        print(f"\nHabitica Daily Tasks Report for {datetime.now().strftime('%Y-%m-%d')}")
        print("-" * 50)
        
        if incomplete:
            print("\nIncomplete tasks:")
            for task in incomplete:
                # Get checklist status if present
                checklist = task.get('checklist', [])
                checklist_done = len([item for item in checklist if item.get('completed', False)])
                checklist_total = len(checklist)
                
                # Format task with checklist info if present
                if checklist:
                    print(f"• {prettify(task['text'])} ({checklist_done}/{checklist_total} subtasks)")
                else:
                    print(f"• {prettify(task['text'])}")
        
        if completed:
            print("\nCompleted tasks:")
            for task in completed:
                print(f"✓ {prettify(task['text'])}")
                
        print(f"\nProgress: {len(completed)}/{len(completed) + len(incomplete)} tasks completed")

    return incomplete, completed

def main():
    """Main entry point"""
    incomplete, completed = check_daily_tasks()
    
    # Exit with status code based on completion
    if incomplete:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main() 