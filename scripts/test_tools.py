"""Test forecasting tools independently."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.agent.forecasting_tools import (
    perplexity_web_research,
    asknews_search,
    execute_squiggle,
    write_markdown_report,
)


async def test_perplexity():
    """Test Perplexity tool."""
    print("\n" + "="*80)
    print("TEST 1: Perplexity Web Research")
    print("="*80)

    # Call the handler method of the SdkMcpTool
    result = await perplexity_web_research.handler({
        "query": "Google Gemini 2.0 release December 2024 features",
        "focus": "exact_data"
    })

    content = result.get("content", [{}])[0].get("text", "")
    is_error = result.get("isError", False)

    if is_error:
        print(f"❌ FAILED: {content}")
        return False
    else:
        print(f"✅ PASSED")
        print(f"Response preview: {content[:300]}...")
        return True


async def test_asknews():
    """Test AskNews tool."""
    print("\n" + "="*80)
    print("TEST 2: AskNews Search")
    print("="*80)

    result = await asknews_search.handler({
        "query": "AI model releases 2024",
        "days_back": 60,
        "focus": "announcements"
    })

    content = result.get("content", [{}])[0].get("text", "")
    is_error = result.get("isError", False)

    if is_error:
        print(f"❌ FAILED: {content}")
        return False
    else:
        print(f"✅ PASSED")
        print(f"Response preview: {content[:300]}...")
        return True


async def test_squiggle():
    """Test Squiggle execution."""
    print("\n" + "="*80)
    print("TEST 3: Squiggle Code Execution")
    print("="*80)

    squiggle_code = """
// Simple probability calculation
baseRate = 0.5
adjustment = 0.1
forecast = baseRate + adjustment
forecast
"""

    result = await execute_squiggle.handler({
        "code": squiggle_code,
        "model_name": "test_model"
    })

    content = result.get("content", [{}])[0].get("text", "")
    is_error = result.get("isError", False)

    if is_error:
        print(f"❌ FAILED: {content}")
        return False
    else:
        print(f"✅ PASSED (or Squiggle CLI not installed)")
        print(f"Response: {content[:300]}...")
        return True


async def test_markdown():
    """Test markdown writing."""
    print("\n" + "="*80)
    print("TEST 4: Markdown Report Writing")
    print("="*80)

    result = await write_markdown_report.handler({
        "filepath": "research_reports/test_tool_report.md",
        "title": "Tool Test Report",
        "content": "# Test Content\n\nThis is a test of the markdown writing tool.\n\n## Models\n\n- Model 1: Base rate\n- Model 2: Trend analysis"
    })

    content = result.get("content", [{}])[0].get("text", "")
    is_error = result.get("isError", False)

    if is_error:
        print(f"❌ FAILED: {content}")
        return False
    else:
        print(f"✅ PASSED")
        print(f"Response: {content}")
        return True


async def main():
    """Run all tests."""
    print("="*80)
    print("FORECASTING TOOLS TEST SUITE")
    print("="*80)
    print("\nTesting 4 tools:")
    print("1. perplexity_web_research")
    print("2. asknews_search")
    print("3. execute_squiggle")
    print("4. write_markdown_report")

    results = {}

    # Test each tool
    results["perplexity"] = await test_perplexity()
    results["asknews"] = await test_asknews()
    results["squiggle"] = await test_squiggle()
    results["markdown"] = await test_markdown()

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Tools are working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check error messages above.")
        print("\nCommon fixes:")
        print("- Perplexity: Set PERPLEXITY_API_KEY in .env")
        print("- AskNews: Set ASKNEWS_CLIENT_ID and ASKNEWS_CLIENT_SECRET in .env")
        print("- Squiggle: Install with 'npm install -g @quantified-uncertainty/squiggle-cli'")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
