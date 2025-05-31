# app/services/tariff_service.py
import logging
from datetime import datetime, time
from app.db.database import execute_query

logger = logging.getLogger("ocpp.tariff")

class TariffService:
    @staticmethod
    def calculate_session_cost(pricing_plan_id, energy_kwh, session_start, session_end):
        """
        Calculate cost based on tariff and energy consumption.
        
        Args:
            pricing_plan_id (int): ID of the pricing plan/tariff
            energy_kwh (float): Total energy consumed in kWh
            session_start (str): Session start timestamp
            session_end (str): Session end timestamp
            
        Returns:
            tuple: (total_cost, breakdown_dict)
        """
        try:
            if not pricing_plan_id or energy_kwh <= 0:
                return 0.0, {"reason": "No pricing plan or zero energy"}
            
            # Get tariff details
            tariff = execute_query(
                """
                SELECT TariffsRateDaytime, TariffsRateNighttime, TariffsDaytimeFrom, 
                       TariffsDaytimeTo, TariffsNighttimeFrom, TariffsNighttimeTo,
                       TariffsFixedStartFee, TariffsType, TariffsPer, TariffsName
                FROM Tariffs 
                WHERE TariffsId = ? AND TariffsEnabled = 1
                """,
                (pricing_plan_id,)
            )
            
            if not tariff:
                logger.warning(f"Tariff {pricing_plan_id} not found or disabled")
                return 0.0, {"error": "Tariff not found"}
            
            tariff_data = tariff[0]
            breakdown = {
                "tariff_name": tariff_data["TariffsName"],
                "energy_kwh": energy_kwh,
                "tariff_type": tariff_data["TariffsType"],
                "pricing_per": tariff_data["TariffsPer"]
            }
            
            total_cost = 0.0
            
            # Add fixed start fee if applicable
            if tariff_data["TariffsFixedStartFee"]:
                total_cost += float(tariff_data["TariffsFixedStartFee"])
                breakdown["fixed_start_fee"] = float(tariff_data["TariffsFixedStartFee"])
            
            # Calculate energy cost based on time-of-use if both day/night rates are available
            if (tariff_data["TariffsRateDaytime"] and tariff_data["TariffsRateNighttime"] and
                tariff_data["TariffsDaytimeFrom"] and tariff_data["TariffsDaytimeTo"]):
                
                energy_cost = TariffService._calculate_time_based_cost(
                    energy_kwh, session_start, session_end, tariff_data
                )
                breakdown.update(energy_cost["breakdown"])
                total_cost += energy_cost["cost"]
                
            elif tariff_data["TariffsRateDaytime"]:
                # Use daytime rate as default rate
                energy_cost = energy_kwh * float(tariff_data["TariffsRateDaytime"])
                total_cost += energy_cost
                breakdown["energy_cost"] = energy_cost
                breakdown["rate_used"] = float(tariff_data["TariffsRateDaytime"])
                breakdown["rate_type"] = "flat_rate"
            
            breakdown["total_cost"] = round(total_cost, 2)
            
            logger.info(f"Cost calculated: ${total_cost:.2f} for {energy_kwh} kWh using tariff {pricing_plan_id}")
            return round(total_cost, 2), breakdown
            
        except Exception as e:
            logger.error(f"Error calculating session cost: {str(e)}")
            return 0.0, {"error": str(e)}
    
    @staticmethod
    def _calculate_time_based_cost(energy_kwh, session_start, session_end, tariff_data):
        """
        Calculate cost based on time-of-use rates.
        Simplified implementation - assumes uniform energy consumption during session.
        """
        try:
            # Parse times
            daytime_from = datetime.strptime(tariff_data["TariffsDaytimeFrom"], "%H:%M:%S").time()
            daytime_to = datetime.strptime(tariff_data["TariffsDaytimeTo"], "%H:%M:%S").time()
            
            # Parse session timestamps
            start_dt = datetime.fromisoformat(session_start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(session_end.replace('Z', '+00:00'))
            
            # Get start and end times (ignore date for simplicity)
            start_time = start_dt.time()
            end_time = end_dt.time()
            
            # Simple heuristic: if session starts during daytime, use daytime rate
            # Otherwise use nighttime rate
            # In a more complex implementation, you'd calculate the exact proportion
            if TariffService._is_daytime(start_time, daytime_from, daytime_to):
                rate = float(tariff_data["TariffsRateDaytime"])
                rate_type = "daytime"
            else:
                rate = float(tariff_data["TariffsRateNighttime"])
                rate_type = "nighttime"
            
            energy_cost = energy_kwh * rate
            
            return {
                "cost": energy_cost,
                "breakdown": {
                    "energy_cost": energy_cost,
                    "rate_used": rate,
                    "rate_type": rate_type,
                    "session_start_time": start_time.strftime("%H:%M:%S"),
                    "daytime_hours": f"{daytime_from.strftime('%H:%M')}-{daytime_to.strftime('%H:%M')}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error in time-based cost calculation: {str(e)}")
            # Fallback to daytime rate
            rate = float(tariff_data["TariffsRateDaytime"])
            energy_cost = energy_kwh * rate
            return {
                "cost": energy_cost,
                "breakdown": {
                    "energy_cost": energy_cost,
                    "rate_used": rate,
                    "rate_type": "fallback_daytime",
                    "error": str(e)
                }
            }
    
    @staticmethod
    def _is_daytime(check_time, daytime_from, daytime_to):
        """Check if given time falls within daytime hours"""
        if daytime_from <= daytime_to:
            # Normal case: 08:00 to 18:00
            return daytime_from <= check_time <= daytime_to
        else:
            # Overnight case: 22:00 to 06:00 (nighttime rate during day)
            return not (daytime_to < check_time < daytime_from)