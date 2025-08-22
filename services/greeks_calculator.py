#!/usr/bin/env python3

import numpy as np
from scipy.stats import norm
import math
from datetime import datetime, date

class GreeksCalculator:
    """
    Calculate option Greeks using Black-Scholes model
    """
    
    def __init__(self, risk_free_rate=0.05):
        """
        Initialize Greeks calculator
        
        Args:
            risk_free_rate: Risk-free interest rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
    
    def _safe_float(self, value, default=0):
        """Safely convert value to float, handling tuples from Kite API"""
        try:
            if isinstance(value, (list, tuple)):
                value = value[0] if value else default
            return float(value) if value is not None else default
        except (ValueError, TypeError, IndexError):
            return default
    
    def _d1(self, S, K, T, r, sigma):
        """Calculate d1 parameter for Black-Scholes"""
        # Convert inputs to float scalars (handle tuples from Kite API)
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
            
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0
        return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    
    def _d2(self, S, K, T, r, sigma):
        """Calculate d2 parameter for Black-Scholes"""
        # Convert inputs to float scalars (handle tuples from Kite API)
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
            
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0
        return self._d1(S, K, T, r, sigma) - sigma * np.sqrt(T)
    
    def calculate_time_to_expiry(self, expiry_date):
        """
        Calculate time to expiry in years
        
        Args:
            expiry_date: Expiry date (datetime, date, or string YYYY-MM-DD)
        
        Returns:
            Time to expiry in years
        """
        if isinstance(expiry_date, str):
            expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
        elif isinstance(expiry_date, datetime):
            expiry_date = expiry_date.date()
        
        today = date.today()
        days_to_expiry = (expiry_date - today).days
        
        # Convert to years (assuming 365 days per year)
        return max(days_to_expiry / 365.0, 0.001)  # Minimum 0.001 to avoid division by zero
    
    def calculate_implied_volatility_estimate(self, option_price, S, K, T, r, option_type='CE'):
        """
        Estimate implied volatility using Newton-Raphson method
        This is a simplified version - in practice, more sophisticated methods are used
        
        Args:
            option_price: Current option price
            S: Spot price
            K: Strike price
            T: Time to expiry in years
            r: Risk-free rate
            option_type: 'CE' for Call, 'PE' for Put
        
        Returns:
            Estimated implied volatility
        """
        if option_price <= 0 or S <= 0 or K <= 0 or T <= 0:
            return 0.2  # Default 20% volatility
        
        # Initial guess
        sigma = 0.2
        
        # Newton-Raphson iterations
        for i in range(10):  # Limit iterations
            try:
                if option_type == 'CE':
                    theo_price = self.black_scholes_call(S, K, T, r, sigma)
                    vega = self.calculate_vega(S, K, T, r, sigma)
                else:
                    theo_price = self.black_scholes_put(S, K, T, r, sigma)
                    vega = self.calculate_vega(S, K, T, r, sigma)
                
                price_diff = theo_price - option_price
                
                if abs(price_diff) < 0.01 or vega < 0.001:  # Convergence criteria
                    break
                    
                sigma = sigma - price_diff / (vega * 100)  # vega is per 1% change
                sigma = max(sigma, 0.01)  # Minimum 1% volatility
                
            except:
                break
        
        return max(sigma, 0.01)  # Return minimum 1% volatility
    
    def black_scholes_call(self, S, K, T, r, sigma):
        """Calculate Black-Scholes call option price"""
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
        
        if T <= 0:
            return max(S - K, 0)
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(S, K, T, r, sigma)
        
        call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return max(call_price, 0)
    
    def black_scholes_put(self, S, K, T, r, sigma):
        """Calculate Black-Scholes put option price"""
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
        
        if T <= 0:
            return max(K - S, 0)
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(S, K, T, r, sigma)
        
        put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return max(put_price, 0)
    
    def calculate_delta(self, S, K, T, r, sigma, option_type='CE'):
        """
        Calculate Delta (price sensitivity to underlying price change)
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry in years
            r: Risk-free rate
            sigma: Implied volatility
            option_type: 'CE' for Call, 'PE' for Put
        
        Returns:
            Delta value
        """
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
        
        if T <= 0:
            if option_type == 'CE':
                return 1.0 if S > K else 0.0
            else:
                return -1.0 if S < K else 0.0
        
        d1 = self._d1(S, K, T, r, sigma)
        
        if option_type == 'CE':
            return norm.cdf(d1)
        else:
            return norm.cdf(d1) - 1
    
    def calculate_gamma(self, S, K, T, r, sigma):
        """
        Calculate Gamma (rate of change of Delta)
        
        Returns:
            Gamma value
        """
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
        
        if T <= 0 or sigma <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        return norm.pdf(d1) / (S * sigma * np.sqrt(T))
    
    def calculate_vega(self, S, K, T, r, sigma):
        """
        Calculate Vega (sensitivity to volatility change)
        
        Returns:
            Vega value (per 1% change in volatility)
        """
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
        
        if T <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        return S * norm.pdf(d1) * np.sqrt(T) / 100  # Divided by 100 for per 1% change
    
    def calculate_theta(self, S, K, T, r, sigma, option_type='CE'):
        """
        Calculate Theta (time decay)
        
        Returns:
            Theta value (per day)
        """
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
        
        if T <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(S, K, T, r, sigma)
        
        if option_type == 'CE':
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                    - r * K * np.exp(-r * T) * norm.cdf(d2))
        else:
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                    + r * K * np.exp(-r * T) * norm.cdf(-d2))
        
        return theta / 365  # Convert to per day
    
    def calculate_rho(self, S, K, T, r, sigma, option_type='CE'):
        """
        Calculate Rho (sensitivity to interest rate change)
        
        Returns:
            Rho value (per 1% change in interest rate)
        """
        S = self._safe_float(S)
        K = self._safe_float(K)
        T = self._safe_float(T)
        r = self._safe_float(r)
        sigma = self._safe_float(sigma)
        
        if T <= 0:
            return 0
        
        d2 = self._d2(S, K, T, r, sigma)
        
        if option_type == 'CE':
            rho = K * T * np.exp(-r * T) * norm.cdf(d2)
        else:
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2)
        
        return rho / 100  # Convert to per 1% change
    
    def calculate_all_greeks(self, S, K, T, r, sigma, option_type='CE', option_price=None):
        """
        Calculate all Greeks for an option
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry in years
            r: Risk-free rate
            sigma: Implied volatility (if None and option_price provided, will estimate)
            option_type: 'CE' for Call, 'PE' for Put
            option_price: Current option price (for IV estimation if sigma is None)
        
        Returns:
            Dictionary with all Greeks
        """
        try:
            # Convert all inputs to float and handle edge cases
            S = self._safe_float(S)
            K = self._safe_float(K)
            T = self._safe_float(T)
            r = self._safe_float(r, 0.05)
            
            # Handle sigma input
            sigma = self._safe_float(sigma)
            
            # Handle option_price input  
            option_price = self._safe_float(option_price)
            
            # Validate inputs
            if S <= 0 or K <= 0 or T <= 0:
                return {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0, 'rho': 0, 'iv': 0}
            
            # If no IV provided, estimate it from option price
            if sigma <= 0:
                if option_price and option_price > 0:
                    sigma = self.calculate_implied_volatility_estimate(option_price, S, K, T, r, option_type)
                else:
                    sigma = 0.2  # Default 20% volatility
            
            greeks = {
                'delta': self.calculate_delta(S, K, T, r, sigma, option_type),
                'gamma': self.calculate_gamma(S, K, T, r, sigma),
                'vega': self.calculate_vega(S, K, T, r, sigma),
                'theta': self.calculate_theta(S, K, T, r, sigma, option_type),
                'rho': self.calculate_rho(S, K, T, r, sigma, option_type),
                'iv': sigma
            }
            
            return greeks
            
        except Exception as e:
            # Return zeros if calculation fails
            return {
                'delta': 0,
                'gamma': 0,
                'vega': 0,
                'theta': 0,
                'rho': 0,
                'iv': 0
            }
    
    def calculate_analytics(self, S, K, option_price, option_type='CE'):
        """
        Calculate option analytics: intrinsic value, time value, WTB%, WTT%, entry signals
        
        Args:
            S: Spot price
            K: Strike price
            option_price: Current option price
            option_type: 'CE' for Call, 'PE' for Put
        
        Returns:
            Dictionary with analytics
        """
        try:
            S = self._safe_float(S)
            K = self._safe_float(K)
            option_price = self._safe_float(option_price)
            
            # Calculate intrinsic value
            if option_type == 'CE':
                intrinsic = max(0, S - K)
            else:
                intrinsic = max(0, K - S)
            
            # Calculate time value
            time_value = max(0, option_price - intrinsic)
            
            # Calculate percentages
            if option_price > 0:
                wtb_percent = (intrinsic / option_price) * 100  # Worth to Buy %
                wtt_percent = (time_value / option_price) * 100  # Worth to Time %
            else:
                wtb_percent = 0
                wtt_percent = 0
            
            # Calculate target and stop loss
            target_price = option_price * 1.4  # 40% profit target
            stop_loss = option_price * 0.7     # 30% stop loss
            
            return {
                'intrinsic': intrinsic,
                'time_value': time_value,
                'wtb_percent': wtb_percent,
                'wtt_percent': wtt_percent,
                'target_price': target_price,
                'stop_loss': stop_loss
            }
            
        except Exception as e:
            return {
                'intrinsic': 0,
                'time_value': 0,
                'wtb_percent': 0,
                'wtt_percent': 0,
                'target_price': 0,
                'stop_loss': 0
            }
    
    def calculate_entry_signal(self, delta, iv, wtb_percent):
        """
        Calculate entry signal based on delta, IV, and WTB%
        
        Args:
            delta: Option delta
            iv: Implied volatility (as decimal, e.g., 0.2 for 20%)
            wtb_percent: Worth to Buy percentage
        
        Returns:
            Entry signal: 'BUY', 'SELL', or 'HOLD'
        """
        try:
            delta = self._safe_float(delta)
            iv = self._safe_float(iv)
            wtb_percent = self._safe_float(wtb_percent)
            
            # Entry signal logic from Streamlit code
            if wtb_percent > 50 and abs(delta) > 0.6 and iv < 0.3:
                return "BUY"
            elif wtb_percent < 20 and abs(delta) < 0.3:
                return "SELL"
            else:
                return "HOLD"
                
        except Exception as e:
            return "HOLD"

# Test the calculator
if __name__ == "__main__":
    calc = GreeksCalculator()
    
    # Test with sample data
    S = 25000  # NIFTY spot
    K = 25000  # ATM strike
    T = 0.1    # ~36 days to expiry
    r = 0.05   # 5% risk-free rate
    sigma = 0.15  # 15% volatility
    
    print("Testing Greeks Calculator:")
    print(f"Spot: {S}, Strike: {K}, Time: {T:.3f} years, Vol: {sigma:.1%}")
    
    # Test Call option
    ce_greeks = calc.calculate_all_greeks(S, K, T, r, sigma, 'CE')
    print(f"\nCall Option Greeks:")
    for greek, value in ce_greeks.items():
        print(f"  {greek.upper()}: {value:.4f}")
    
    # Test Put option
    pe_greeks = calc.calculate_all_greeks(S, K, T, r, sigma, 'PE')
    print(f"\nPut Option Greeks:")
    for greek, value in pe_greeks.items():
        print(f"  {greek.upper()}: {value:.4f}")
