import time
import gc

class DataManager:
    def __init__(self, max_hours=24):
        self.max_hours = max_hours
        self.max_points = (max_hours * 60 * 60) // 15  # Data point every 15 seconds
        
        # Use separate lists for memory efficiency
        self.timestamps = []
        self.pv_power = []
        self.grid_power = []
        self.battery_power = []
        self.load_power = []
        
    def add_data_point(self, data):
        """Add a new data point and remove old ones if necessary"""
        # Add timestamp if not present
        timestamp = data.get('timestamp', time.time())
        
        # Add new data point to lists
        self.timestamps.append(timestamp)
        self.pv_power.append(data.get('pv_power', 0))
        self.grid_power.append(data.get('grid_power', 0))
        self.battery_power.append(data.get('battery_power', 0))
        self.load_power.append(data.get('load_power', 0))
        
        # Remove old data points
        current_time = time.time()
        cutoff_time = current_time - (self.max_hours * 60 * 60)
        
        # Find cutoff index
        cutoff_idx = 0
        while cutoff_idx < len(self.timestamps) and self.timestamps[cutoff_idx] <= cutoff_time:
            cutoff_idx += 1
        
        # Remove old data efficiently
        if cutoff_idx > 0:
            del self.timestamps[:cutoff_idx]
            del self.pv_power[:cutoff_idx]
            del self.grid_power[:cutoff_idx]
            del self.battery_power[:cutoff_idx]
            del self.load_power[:cutoff_idx]
        
        # Garbage collection to manage memory
        if len(self.timestamps) % 100 == 0:
            gc.collect()
            
    def get_averages(self, time_window):
        """Calculate average power values over the specified time window (in seconds)"""
        if not self.timestamps:
            return {
                'pv_power': 0,
                'grid_import': 0,
                'grid_export': 0,
                'battery_power': 0,
                'load_power': 0
            }
            
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        # Find start index for time window
        start_idx = 0
        while start_idx < len(self.timestamps) and self.timestamps[start_idx] <= cutoff_time:
            start_idx += 1
        
        if start_idx >= len(self.timestamps):
            return {
                'pv_power': 0,
                'grid_import': 0,
                'grid_export': 0,
                'battery_power': 0,
                'load_power': 0
            }
            
        # Calculate averages using slices
        num_points = len(self.timestamps) - start_idx
        totals = {
            'pv_power': 0,
            'grid_import': 0,
            'grid_export': 0,
            'battery_power': 0,
            'load_power': 0
        }
        
        for i in range(start_idx, len(self.timestamps)):
            totals['pv_power'] += self.pv_power[i]
            
            # Separate grid power into import and export
            grid_power = self.grid_power[i]
            if grid_power > 0:
                totals['grid_import'] += grid_power
            else:
                totals['grid_export'] += abs(grid_power)
                
            totals['battery_power'] += self.battery_power[i]
            totals['load_power'] += self.load_power[i]
                
        averages = {}
        for key in totals:
            averages[key] = totals[key] / num_points if num_points > 0 else 0
            
        return averages
        
    def calculate_self_sufficiency(self, time_window):
        """Calculate degree of self-sufficiency over the specified time window"""
        if not self.timestamps:
            return 0.0
            
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        # Find start index for time window
        start_idx = 0
        while start_idx < len(self.timestamps) and self.timestamps[start_idx] <= cutoff_time:
            start_idx += 1
        
        if start_idx >= len(self.timestamps):
            return 0.0
            
        # Calculate total energy consumption and grid import
        total_consumption = 0
        total_grid_import = 0
        
        for i in range(start_idx, len(self.timestamps)):
            # Load power (consumption)
            load_power = abs(self.load_power[i])
            
            # Grid power (positive when importing from grid, negative when exporting)
            grid_power = self.grid_power[i]
            grid_import = max(0, grid_power)  # Only positive values (import)
            
            # Time interval (simplified - assuming 15 seconds between points)
            if i < len(self.timestamps) - 1:
                time_interval = self.timestamps[i + 1] - self.timestamps[i]
            else:
                time_interval = 15  # Default interval
                
            total_consumption += load_power * time_interval
            total_grid_import += grid_import * time_interval
            
        # Calculate self-sufficiency: (consumption - grid_import) / consumption
        if total_consumption > 0:
            self_sufficiency = ((total_consumption - total_grid_import) / total_consumption) * 100
            # Cap at 100% and ensure not negative
            return max(0.0, min(self_sufficiency, 100.0))
        else:
            return 0.0
            
    def get_load_history(self, time_window):
        """Get load power history for charting - return all data points for bar chart"""
        if not self.timestamps:
            return []
            
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        # Find start index for time window
        start_idx = 0
        while start_idx < len(self.timestamps) and self.timestamps[start_idx] <= cutoff_time:
            start_idx += 1
        
        if start_idx >= len(self.timestamps):
            return []
            
        # Extract load power values using slice
        load_values = [abs(self.load_power[i]) for i in range(start_idx, len(self.timestamps))]
        
        # Return all data points - chart will handle aggregation
        return load_values
            
    def get_latest_data(self):
        """Get the most recent data point"""
        if not self.timestamps:
            return None
        
        return {
            'pv_power': self.pv_power[-1],
            'grid_power': self.grid_power[-1],
            'battery_power': self.battery_power[-1],
            'load_power': self.load_power[-1],
            'timestamp': self.timestamps[-1]
        }
        
    def get_data_count(self):
        """Get the number of stored data points"""
        return len(self.timestamps)
        
    def clear_old_data(self, hours_to_keep):
        """Clear data older than specified hours"""
        current_time = time.time()
        cutoff_time = current_time - (hours_to_keep * 60 * 60)
        
        # Find cutoff index
        cutoff_idx = 0
        while cutoff_idx < len(self.timestamps) and self.timestamps[cutoff_idx] <= cutoff_time:
            cutoff_idx += 1
        
        # Remove old data efficiently
        if cutoff_idx > 0:
            del self.timestamps[:cutoff_idx]
            del self.pv_power[:cutoff_idx]
            del self.grid_power[:cutoff_idx]
            del self.battery_power[:cutoff_idx]
            del self.load_power[:cutoff_idx]
        
        gc.collect()
