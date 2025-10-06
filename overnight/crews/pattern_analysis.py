"""
Pattern analysis crew for overnight intelligence system.

Handles energy consumption analysis and pattern detection.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..schemas import (
    PatternAnalysisOutput,
    EnergyInsight
)
from ..tools import (
    energy_tools,
    memory_tools
)
from ..guards import GuardRails

logger = logging.getLogger(__name__)


class EnergyAuditorAgent:
    """
    Agent for analyzing home energy consumption.
    
    This agent:
    1. Fetches energy consumption data from HA Energy Dashboard
    2. Identifies high-consumption devices
    3. Detects anomalies vs. weekly average
    4. Generates actionable insights
    """
    
    def __init__(self):
        self.guards = GuardRails()
        logger.info("Initialized EnergyAuditorAgent")
    
    async def analyze_daily_energy(self) -> List[EnergyInsight]:
        """
        Analyze yesterday's energy consumption.
        
        Returns:
            List of energy insights
        """
        try:
            insights = []
            
            # Get 24h energy consumption
            logger.info("Fetching 24h energy consumption...")
            consumption_data = await energy_tools.get_energy_consumption_24h()
            total_kwh = consumption_data.get("total_kwh", 0.0)
            
            if total_kwh == 0:
                logger.warning("No energy consumption data available")
                return [EnergyInsight(
                    title="No Energy Data",
                    description="Unable to retrieve energy consumption data from Home Assistant.",
                    severity="warning"
                )]
            
            logger.info(f"Total 24h consumption: {total_kwh:.2f} kWh")
            
            # Get device breakdown
            logger.info("Fetching device energy breakdown...")
            device_breakdown = await energy_tools.get_device_energy_breakdown()
            
            # Get weekly average
            logger.info("Fetching weekly average consumption...")
            weekly_avg = await energy_tools.get_weekly_average_consumption()
            
            # Insight 1: Compare to weekly average
            deviation_percent = ((total_kwh - weekly_avg) / weekly_avg) * 100 if weekly_avg > 0 else 0
            
            if abs(deviation_percent) >= 20:
                severity = "warning" if deviation_percent > 0 else "info"
                direction = "higher" if deviation_percent > 0 else "lower"
                insights.append(EnergyInsight(
                    title=f"{direction.title()} Than Average Consumption",
                    description=f"Yesterday's energy consumption was {total_kwh:.2f} kWh, which is {abs(deviation_percent):.1f}% {direction} than the weekly average of {weekly_avg:.2f} kWh/day.",
                    severity=severity,
                    energy_kwh=total_kwh,
                    time_period="24h"
                ))
            else:
                insights.append(EnergyInsight(
                    title="Normal Energy Consumption",
                    description=f"Yesterday's energy consumption of {total_kwh:.2f} kWh is within normal range (weekly average: {weekly_avg:.2f} kWh/day).",
                    severity="info",
                    energy_kwh=total_kwh,
                    time_period="24h"
                ))
            
            # Insight 2: Top energy consumers
            if device_breakdown:
                top_devices = device_breakdown[:3]  # Top 3 consumers
                total_device_kwh = sum(d["consumption_kwh"] for d in device_breakdown)
                
                for idx, device in enumerate(top_devices, 1):
                    device_name = device["device_name"]
                    device_kwh = device["consumption_kwh"]
                    device_percent = (device_kwh / total_device_kwh * 100) if total_device_kwh > 0 else 0
                    
                    # Alert on unusually high consumption
                    severity = "warning" if device_percent > 40 else "info"
                    
                    insights.append(EnergyInsight(
                        title=f"#{idx} Energy Consumer: {device_name}",
                        description=f"{device_name} consumed {device_kwh:.2f} kWh ({device_percent:.1f}% of total) in the last 24 hours.",
                        severity=severity,
                        device_name=device_name,
                        energy_kwh=device_kwh,
                        time_period="24h"
                    ))
            
            # Insight 3: Identify devices with anomalous consumption
            if device_breakdown:
                for device in device_breakdown:
                    device_name = device["device_name"]
                    device_kwh = device["consumption_kwh"]
                    
                    # Simple heuristic: Alert if a single device uses >50% of total
                    if total_kwh > 0 and (device_kwh / total_kwh) > 0.5:
                        insights.append(EnergyInsight(
                            title=f"High {device_name} Usage Detected",
                            description=f"{device_name} consumed {device_kwh:.2f} kWh, which is over 50% of total daily consumption. This may indicate extended runtime or inefficiency.",
                            severity="warning",
                            device_name=device_name,
                            energy_kwh=device_kwh,
                            time_period="24h"
                        ))
            
            # Insight 4: Energy efficiency recommendations
            if total_kwh > 30:  # High consumption threshold
                insights.append(EnergyInsight(
                    title="High Daily Consumption Detected",
                    description=f"Daily consumption of {total_kwh:.2f} kWh is relatively high. Consider reviewing device schedules and automation rules for energy savings opportunities.",
                    severity="warning",
                    energy_kwh=total_kwh,
                    time_period="24h"
                ))
            
            logger.info(f"Generated {len(insights)} energy insights")
            return insights
            
        except Exception as e:
            logger.error(f"Failed to analyze energy consumption: {e}")
            return [EnergyInsight(
                title="Energy Analysis Failed",
                description=f"Failed to analyze energy consumption: {str(e)}",
                severity="warning"
            )]
    
    async def correlate_energy_spikes(
        self,
        device_breakdown: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Correlate energy spikes with specific devices.
        
        Args:
            device_breakdown: List of device consumption data
            
        Returns:
            List of correlation insights
        """
        correlations = []
        
        try:
            # Find devices responsible for high consumption periods
            # This is a simplified version - in production, you'd analyze
            # time-series data to find actual spikes
            
            if not device_breakdown:
                return []
            
            # Sort by consumption
            sorted_devices = sorted(
                device_breakdown,
                key=lambda x: x["consumption_kwh"],
                reverse=True
            )
            
            # Top device analysis
            if sorted_devices:
                top_device = sorted_devices[0]
                device_name = top_device["device_name"]
                device_kwh = top_device["consumption_kwh"]
                
                correlations.append(
                    f"Primary consumption driver: {device_name} ({device_kwh:.2f} kWh)"
                )
            
            # Check for multiple high-consumption devices
            high_consumers = [d for d in sorted_devices if d["consumption_kwh"] > 5.0]
            if len(high_consumers) > 1:
                device_names = ", ".join(d["device_name"] for d in high_consumers[:3])
                correlations.append(
                    f"Multiple high-consumption devices detected: {device_names}"
                )
            
            return correlations
            
        except Exception as e:
            logger.error(f"Failed to correlate energy spikes: {e}")
            return []


class PatternAnalysisCrew:
    """
    Crew for pattern analysis operations.
    
    This crew:
    1. Analyzes energy consumption patterns
    2. Detects anomalies and trends
    3. Generates actionable insights
    4. Creates analysis reports
    """
    
    def __init__(self):
        self.energy_auditor = EnergyAuditorAgent()
        self.guards = GuardRails()
        logger.info("Initialized PatternAnalysisCrew")
    
    async def run_daily_analysis(self) -> PatternAnalysisOutput:
        """
        Run daily pattern analysis cycle.
        
        Returns:
            PatternAnalysisOutput with analysis results
        """
        task_id = str(uuid.uuid4())
        logger.info(f"Starting pattern analysis cycle (id: {task_id})")
        
        try:
            # Check rate limits
            self.guards.check_rate_limit("analysis", max_per_hour=20, max_per_minute=2)
            
            # Analyze energy consumption
            logger.info("Running energy analysis...")
            energy_insights = await self.energy_auditor.analyze_daily_energy()
            
            # Get consumption data for summary
            consumption_data = await energy_tools.get_energy_consumption_24h()
            total_kwh = consumption_data.get("total_kwh", 0.0)
            
            # Create summary
            yesterday = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
            summary_parts = [
                f"Pattern Analysis for {yesterday}:",
                f"- Total Energy Consumption: {total_kwh:.2f} kWh",
                f"- {len(energy_insights)} insights generated",
            ]
            
            # Categorize insights by severity
            warnings = [i for i in energy_insights if i.severity == "warning"]
            infos = [i for i in energy_insights if i.severity == "info"]
            
            summary_parts.append(f"- {len(warnings)} warnings, {len(infos)} informational insights")
            
            summary = "\n".join(summary_parts)
            
            result = PatternAnalysisOutput(
                task_id=task_id,
                energy_insights=energy_insights,
                analysis_period="24h",
                total_consumption_kwh=total_kwh,
                summary=summary
            )
            
            # Save summary to memory
            try:
                await memory_tools.add_memory(
                    title=f"Energy Analysis - {yesterday}",
                    content=summary + "\n\nKey Insights:\n" + "\n".join(
                        f"- {i.title}: {i.description}" for i in energy_insights[:3]
                    ),
                    mem_type="insight",
                    tier="medium",
                    tags=["energy", "analysis", "pattern"],
                    confidence=0.85
                )
                logger.info("Saved energy analysis to memory")
            except Exception as e:
                logger.error(f"Failed to save analysis to memory: {e}")
            
            logger.info(f"Pattern analysis completed: {len(energy_insights)} insights generated")
            return result
            
        except Exception as e:
            logger.error(f"Pattern analysis failed: {e}")
            return PatternAnalysisOutput(
                task_id=task_id,
                energy_insights=[],
                analysis_period="24h",
                total_consumption_kwh=0.0,
                summary=f"Analysis failed: {str(e)}"
            )


from datetime import timedelta
