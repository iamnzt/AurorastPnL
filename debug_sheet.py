import pandas as pd
import io
import requests

def debug_data_loading():
    sheet_id = "1NUpmMswEtKyX1AIeM9p1m8VHjWpPnR8VeJfr1m7Qgsg"
    gid = "1677404640"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    print(f"Fetching from: {url}")
    try:
        # fetch using requests first to see raw content if needed, but pandas usually handles it
        df = pd.read_csv(url)
        print("\n--- Raw DataFrame Head ---")
        print(df.head())
        print("\n--- Columns ---")
        print(df.columns.tolist())
        
        print("\n--- Selected Columns (0 and 4) ---")
        try:
            selected = df.iloc[:, [0, 4]].copy()
            selected.columns = ["Name", "Amount"]
            print(selected.head())
            
            print("\n--- Converting Amount to Numeric ---")
            selected["Amount"] = pd.to_numeric(selected["Amount"], errors='coerce').fillna(0)
            print("Non-zero numeric values found:")
            print(selected[selected["Amount"] > 0])
            
            filtered = selected[selected["Amount"] > 100]
            print(f"\n--- Filtered (Amount > 100) Count: {len(filtered)} ---")
            print(filtered)
            
            print(f"\nTotal Sum: {filtered['Amount'].sum()}")
            
        except Exception as e:
            print(f"Error selecting columns: {e}")
            
    except Exception as e:
        print(f"Error reading CSV: {e}")

if __name__ == "__main__":
    debug_data_loading()
