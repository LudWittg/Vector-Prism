"""Initial commit — metadata update
This comment was added to associate the 'Initial commit' with this file.
"""

import argparse

from animation_generator import AnimationGenerator
from animation_planner import AnimationPlanner
from animation_state import HTMLPalette
from svg_decomposition import MultiSVGParser
from utils.setup import (get_models, select_svg_file, set_api_key,
                         setup_logging, title_screen)


def argument_parser():
    parser = argparse.ArgumentParser(description="Animated SVG Generator")
    parser.add_argument('--exp_name', type=str, default='test', help='Experiment name')

    parser.add_argument('--test_json', type=str, default="svg/test.jsonl", help='Path to the test JSONL file')
    parser.add_argument('--test_plan_json', type=str, default="logs/plans.jsonl", help='Path to the test plan JSONL file')

    parser.add_argument('--model_name', type=str, default='gpt-5-mini', help='Model name for LLM and VLM')
    parser.add_argument('--model_provider', type=str, default='openai', help='Model provider (e.g., openai, azure)')
    parser.add_argument('--temperature', type=float, default=1.0, help='Temperature for model sampling')
    parser.add_argument('--base_url', type=str, default=None, help='Base URL for OpenAI-compatible proxy')
    parser.add_argument('--api_key', type=str, default=None, help='API key for the model provider or proxy')

    # VLM-specific settings (for vision tasks like planning and tagging)
    parser.add_argument('--vlm_model', type=str, default=None, help='Model name for VLM (vision tasks). Defaults to --model_name')
    parser.add_argument('--vlm_base_url', type=str, default=None, help='Base URL for VLM. Defaults to --base_url')
    parser.add_argument('--vlm_api_key', type=str, default=None, help='API key for VLM. Defaults to --api_key')

    # LLM-specific settings (for text-only tasks)
    parser.add_argument('--llm_model', type=str, default=None, help='Model name for LLM (text tasks). Defaults to --model_name')
    parser.add_argument('--llm_base_url', type=str, default=None, help='Base URL for LLM. Defaults to --base_url')
    parser.add_argument('--llm_api_key', type=str, default=None, help='API key for LLM. Defaults to --api_key')

    parser.add_argument('--burn_in', type=int, default=2, help='Number of burn-in iterations for SVG parser')
    parser.add_argument('--streaming', action='store_true', help='Enable streaming mode (required by some proxies)')
    
    args = parser.parse_args()
    return args

def main(args):
    # Set up logging
    logger = setup_logging(args)
    logger.info("Starting the animation generation process.")
    set_api_key()

    # Initialize models with separate VLM/LLM configurations
    vlm_model = args.vlm_model or args.model_name
    vlm_base_url = args.vlm_base_url or args.base_url
    vlm_api_key = args.vlm_api_key or args.api_key
    
    llm_model = args.llm_model or args.model_name
    llm_base_url = args.llm_base_url or args.base_url
    llm_api_key = args.llm_api_key or args.api_key
    
    llm, vlm = get_models(
        vlm_model_name=vlm_model,
        llm_model_name=llm_model,
        model_provider=args.model_provider,
        temperature=args.temperature,
        vlm_base_url=vlm_base_url,
        llm_base_url=llm_base_url,
        vlm_api_key=vlm_api_key,
        llm_api_key=llm_api_key,
        streaming=args.streaming,
        logger=logger
    )

    # print("|> Load SVG File")
    svg_path, instruction = select_svg_file(args.test_json)

    # print("|> Plan Animations")
    planner = AnimationPlanner(vlm, logger, load_plan=args.test_plan_json)
    plans = planner.plan(svg_file=svg_path, instruction=instruction)

    logger.info("|> Tagging Semantics")
    svg_parser = MultiSVGParser(vlm, logger)
    svg_parser.set_parser(svg_path, plans)
    if (svg_string:=svg_parser.load_tagged_svg()) is None:
        svg_parser.burn_in(burn_in_count=args.burn_in)
        svg_string = svg_parser.tag_semantics()

    logger.info("|> Generate HTML and CSS scripts")
    animation_state = HTMLPalette(svg_string, logger)
    animator = AnimationGenerator(vlm, logger)
    # reviewer = AnimationReviewer(vlm, logger)
    for class_name in plans.keys():
        logger.info(f"  |=> Animating {class_name}")
        content = {
            'class_name': class_name,
            'viewbox': animation_state.get_viewbox(),
            'animation_plan': plans[class_name],
            'big_picture': svg_parser.full_svg_base64,
            'little_picture': svg_parser.render_by_class(class_name),
        }
        css = animator.animate(content, animation_state.get_current_html())
        animation_state.merge(css)

    animation_state.save_to_html()


if __name__ == "__main__":
    title_screen()
    args = argument_parser()
    main(args)
