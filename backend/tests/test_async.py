#!/usr/bin/env python3
"""
Simple async test
"""

import asyncio

async def simple_test():
    print("Starting async test...")
    await asyncio.sleep(1)
    print("Async test completed!")
    return "success"

if __name__ == "__main__":
    print("Before asyncio.run")
    result = asyncio.run(simple_test())
    print(f"Result: {result}")
    print("After asyncio.run")
