"""
Mender Fleet Simulator - Main Orchestration Script

This script orchestrates multiple simulated Mender devices using asyncio
for efficient concurrent operation.
"""

import asyncio
import signal
import sys
import logging
import argparse
from typing import List, Dict, Optional
from pathlib import Path

from .db.database import DatabaseManager
from .db.models import Device
from .utils.config import load_config, get_enabled_industries, Config
from .utils.crypto import generate_rsa_keypair
from .simulation.profiles import IndustryProfile
from .simulation.device_simulator import DeviceSimulator


# Configure logging
def setup_logging(log_file: str, log_level: str) -> None:
    """Configure logging for the simulator."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


logger = logging.getLogger(__name__)


class FleetOrchestrator:
    """Orchestrates the fleet of simulated devices."""

    def __init__(self, config: Config):
        self.config = config
        self.db: Optional[DatabaseManager] = None
        self.simulators: List[DeviceSimulator] = []
        self.tasks: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Initialize and start all device simulators."""
        logger.info("=" * 60)
        logger.info("Mender Fleet Simulator Starting")
        logger.info("=" * 60)

        # Initialize database
        self.db = DatabaseManager(self.config.simulator.database_path)
        await self.db.connect()

        # Load or create devices
        await self._initialize_devices()

        # Start all simulators
        logger.info(f"Starting {len(self.simulators)} device simulators...")
        for simulator in self.simulators:
            task = asyncio.create_task(simulator.start())
            self.tasks.append(task)

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """Gracefully stop all simulators."""
        logger.info("Initiating graceful shutdown...")

        # Stop all simulators
        for simulator in self.simulators:
            await simulator.stop()

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        # Close database
        if self.db:
            await self.db.close()

        logger.info("Shutdown complete")
        self._shutdown_event.set()

    def signal_shutdown(self) -> None:
        """Signal the orchestrator to shut down."""
        asyncio.create_task(self.stop())

    async def _initialize_devices(self) -> None:
        """Load existing devices or create new ones based on config."""
        enabled_industries = get_enabled_industries(self.config)

        if not enabled_industries:
            logger.warning("No industries enabled in configuration")
            return

        logger.info(f"Enabled industries: {list(enabled_industries.keys())}")

        for industry_name, industry_config in enabled_industries.items():
            profile = IndustryProfile(industry_config)

            # Check existing devices for this industry
            existing = await self.db.get_devices_by_industry(industry_name)
            existing_count = len(existing)
            target_count = industry_config.count

            logger.info(
                f"Industry '{industry_name}': {existing_count} existing, "
                f"{target_count} configured"
            )

            # Create simulators for existing devices
            for device in existing:
                simulator = DeviceSimulator(device, profile, self.config, self.db)
                self.simulators.append(simulator)

            # Create new devices if needed
            if existing_count < target_count:
                new_devices = await self._create_devices(
                    profile,
                    target_count - existing_count,
                    existing_count
                )
                for device in new_devices:
                    simulator = DeviceSimulator(device, profile, self.config, self.db)
                    self.simulators.append(simulator)

        # Summary
        counts = await self.db.count_devices_by_industry()
        total = sum(counts.values())
        logger.info(f"Total devices initialized: {total}")
        for industry, count in counts.items():
            logger.info(f"  - {industry}: {count} devices")

    async def _create_devices(
        self,
        profile: IndustryProfile,
        count: int,
        start_index: int
    ) -> List[Device]:
        """Create new devices for an industry profile."""
        devices = []

        logger.info(f"Creating {count} new devices for {profile.name}")

        for i in range(count):
            index = start_index + i

            # Generate identity
            identity = profile.generate_device_identity(index)
            device_id = f"{profile.config.id_prefix}-{profile.name}-{index:06d}"

            # Generate RSA keypair
            private_key, public_key = generate_rsa_keypair()

            # Generate initial inventory
            inventory = profile.generate_inventory(device_id)

            # Create device
            device = Device(
                device_id=device_id,
                identity_data=identity,
                rsa_private_key=private_key,
                rsa_public_key=public_key,
                industry_profile=profile.name,
                current_status="idle",
                inventory_data=inventory
            )

            # Save to database
            await self.db.save_device(device)
            devices.append(device)

            logger.debug(f"Created device: {device_id}")

        logger.info(f"Created {len(devices)} devices for {profile.name}")
        return devices


async def main(config_path: str) -> None:
    """Main entry point for the simulator."""
    # Load configuration
    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    # Setup logging
    setup_logging(config.simulator.log_file, config.simulator.log_level)

    # Create orchestrator
    orchestrator = FleetOrchestrator(config)

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        logger.info(f"Received signal {sig.name}")
        orchestrator.signal_shutdown()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    # Run orchestrator
    try:
        await orchestrator.start()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        await orchestrator.stop()
        sys.exit(1)


def run():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mender Fleet Simulator - Simulate device fleets for Mender.io"
    )
    parser.add_argument(
        "-c", "--config",
        default="config/config.yaml",
        help="Path to configuration file (default: config/config.yaml)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Mender Fleet Simulator 1.0.0"
    )

    args = parser.parse_args()

    # Run the async main
    asyncio.run(main(args.config))


if __name__ == "__main__":
    run()
