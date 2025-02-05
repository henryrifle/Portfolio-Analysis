import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
import gspread
import csv
import time
import yfinance as yf
from yfinance import download
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from functools import lru_cache

""" Change this to your scope and spreadsheet id that you want to read from.
    You can find the spreadsheet id by going to goolge sheet and highlighint the url in the browser.
    The id is the string of numbers and letters after /d/ and before /edit

    You also need to change the creds.json file that you get from the goolge dev console.
    You can get this by going to the google cloud console and creating a new project.
    Then go to the google sheets api and enable it.
    Then create credentials and download the json file.
    Put that file in the same directory as this file.
"""
SCOPES=["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID="1dZgLXV8w_2cZ5UQNf1jPJXl-fIbVTJ0B5Y6wZ3mqPXo"

# Cache for dividend data to avoid rate limiting
@lru_cache(maxsize=1000)
def get_dividend_info(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        
        
        try:
            hist = stock.history(period="1y")
            if not hist.empty and 'Dividends' in hist.columns:
                annual_div = hist['Dividends'].sum()
                current_price = hist['Close'].iloc[-1]
                if current_price > 0:
                    return annual_div / current_price
        except:
            pass

        try:
            info = stock.fast_info
            if hasattr(info, 'last_dividend') and info.last_dividend:
                annual_div = info.last_dividend * 4  
                current_price = info.last_price
                if current_price > 0:
                    return annual_div / current_price
        except:
            pass

        try:
            info = stock.info
            if 'dividendYield' in info and info['dividendYield'] is not None:
                return info['dividendYield']
            elif 'trailingAnnualDividendYield' in info and info['trailingAnnualDividendYield'] is not None:
                return info['trailingAnnualDividendYield']
            elif 'dividendRate' in info and info['dividendRate'] is not None and 'regularMarketPrice' in info and info['regularMarketPrice'] is not None:
                return info['dividendRate'] / info['regularMarketPrice']
        except:
            pass

        if symbol in ['VTI', 'SCHD', 'VXUS', 'VIG']:
            try:
                hist = stock.history(period="1y")
                if not hist.empty and 'Dividends' in hist.columns:
                    annual_div = hist['Dividends'].sum()
                    current_price = hist['Close'].iloc[-1]
                    if current_price > 0:
                        return annual_div / current_price
            except:
                pass

       
        return 0
    except Exception as e:
        print(f"Error getting dividend for {symbol}: {str(e)}")
        return 0


def gs_reader():
    try:
        credentials = None
        # Delete the token.json file if it exists but is invalid
        if os.path.exists("token.json"):
            try:
                credentials = Credentials.from_authorized_user_file("token.json", SCOPES)
                if not credentials.valid:
                    if credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())
                    else:
                        # If refresh fails, remove the invalid token file
                        os.remove("token.json")
                        credentials = None
            except:
                # If there's any error reading/refreshing the token, remove it
                os.remove("token.json")
                credentials = None

        # If no valid credentials, create new ones
        if not credentials:
            if not os.path.exists("creds.json"):
                raise FileNotFoundError("creds.json file not found. Please ensure you have your Google Sheets credentials file.")
            flow = InstalledAppFlow.from_client_secrets_file("creds.json", SCOPES)
            credentials = flow.run_local_server(port=0)
            # Save the new credentials
            with open("token.json", "w") as token:
                token.write(credentials.to_json())

        spreadsheet_list = ["M1_Finance", "Robinhood", "Schwab"]
        dataframes = {}
        
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        
        # Column mapping for each sheet
        """ This could differ for other spreadsheets"""
        column_mappings = {
            'M1_Finance': {
                'symbol': 0,      # Symbol column index
                'name': 1,        # Name column index
                'equity': 5,      # Equity column index
                'cost': 6,        # Cost column index
                'gl': 7,          # G/L column index
                'allocation': 9,  # Allocation column index
                'annual_div': 10, # Annual Dividend column index
                'div_yield': 11   # Dividend Yield column index
            },
            'Robinhood': {
                'symbol': 0,  # Symbol column index
                'name': 1,    # Name column index
                'equity': 5,  # Equity column index
                'cost': 6,    # Cost column index
                'gl': 7,      # G/L column index
                'allocation': 9  # Allocation column index
            },
            'Schwab': {
                'symbol': 'Ticker',
                'name': 'Name',
                'equity': 'Total Equity',
                'cost': 'Total Cost',
                'gl': 'Total Gain/Loss',
                'allocation': 'Allocation'
            }
        }
        
        for sheet_name in spreadsheet_list:
            try:
                result = sheet.values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{sheet_name}!A1:M41"
                ).execute()
                
                if not result.get("values"):
                    print(f"Warning: No data found in sheet {sheet_name}")
                    continue
                
                df = pd.DataFrame(result.get("values", []))
                if df.empty:
                    print(f"Warning: Empty dataframe for sheet {sheet_name}")
                    continue
                
                print(f"\nDebug: {sheet_name} raw data:")
                print("First row (headers):")
                print(df.iloc[0].tolist())
                print("\nSecond row (first data row):")
                print(df.iloc[1].tolist() if len(df) > 1 else "No data rows")
                
                # Handle headers differently for each sheet and cleaning for the spreadsheets
                """ This could differ for other spreadsheets"""
                if sheet_name == 'Schwab':
                    headers = df.iloc[0]
                    df = df.iloc[1:].reset_index(drop=True)
                    df.columns = headers
                    
                    if 'Name' in df.columns:
                        df['Name'] = df['Name'].apply(lambda x: ' '.join([p for p in str(x).split() if not any(c.isdigit() for c in p) and '%' not in p]))
                else:
                    df[1] = df[1].apply(lambda x: ' '.join([p for p in str(x).split() if not any(c.isdigit() for c in p) and '%' not in p]))
                    df.columns = range(len(df.columns))
                
                print(f"\nDebug: {sheet_name} after setting headers:")
                print("Columns:", df.columns.tolist())
                print("First row:", df.iloc[0].tolist() if not df.empty else "No data")
                
                dataframes[sheet_name] = {
                    'df': df,
                    'mapping': column_mappings[sheet_name]
                }
            except Exception as e:
                print(f"Error reading sheet {sheet_name}: {str(e)}")
                continue

        if not dataframes:
            raise ValueError("No data could be retrieved from any sheets")

        
        total_equity = 0
        total_cost = 0
        total_gl = 0
        
        for account_name, data in dataframes.items():
            try:
                df = data['df']
                mapping = data['mapping']
                if isinstance(mapping['equity'], int):
                    equity = df[mapping['equity']].iloc[-1].replace("$", "").replace(",", "")
                    cost = df[mapping['cost']].iloc[-1].replace("$", "").replace(",", "")
                    gl = df[mapping['gl']].iloc[-1].replace("$", "").replace(",", "")
                else:
                    equity = df[mapping['equity']].iloc[-1].replace("$", "").replace(",", "")
                    cost = df[mapping['cost']].iloc[-1].replace("$", "").replace(",", "")
                    gl = df[mapping['gl']].iloc[-1].replace("$", "").replace(",", "")
                
                total_equity += float(equity)
                total_cost += float(cost)
                total_gl += float(gl)
            except Exception as e:
                print(f"Error processing totals for {account_name}: {str(e)}")

        return total_equity, dataframes

    except FileNotFoundError as e:
        print(f"File error: {str(e)}")
        raise
    except ValueError as e:
        print(f"Value error: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error in gs_reader: {str(e)}")
        raise

def portfolio_analysis(dataframes):
    print("\n=== Portfolio Analysis ===")
    
    # Combine all portfolios for total analysis
    all_holdings = []
    total_portfolio_value = 0
    total_dividend_income = 0
    
    for account_name, data in dataframes.items():
        df = data['df']
        mapping = data['mapping']
        
        
        for i in range(len(df) - 1):
            try:
                row = df.iloc[i]
                if isinstance(mapping['symbol'], int):
                    symbol = str(row[mapping['symbol']]).strip()
                else:
                    symbol = str(row[mapping['symbol']]).strip()
                    
                if symbol and symbol != 'nan':  
                    if isinstance(mapping['equity'], int):
                        equity = float(str(row[mapping['equity']]).replace('$', '').replace(',', '')) if pd.notna(row[mapping['equity']]) else 0
                        cost = float(str(row[mapping['cost']]).replace('$', '').replace(',', '')) if pd.notna(row[mapping['cost']]) else 0
                        gain_loss = float(str(row[mapping['gl']]).replace('$', '').replace(',', '')) if pd.notna(row[mapping['gl']]) else 0
                    else:
                        equity = float(str(row[mapping['equity']]).replace('$', '').replace(',', '')) if pd.notna(row[mapping['equity']]) else 0
                        cost = float(str(row[mapping['cost']]).replace('$', '').replace(',', '')) if pd.notna(row[mapping['cost']]) else 0
                        gain_loss = float(str(row[mapping['gl']]).replace('$', '').replace(',', '')) if pd.notna(row[mapping['gl']]) else 0
                    
                
                    name_raw = str(row[mapping['name']]).strip().split('%')[0].strip()
                    name = ' '.join(name_raw.split())
                    
                    
                    try:
                        allocation_str = str(row[mapping['allocation']]).replace('%', '').strip()
                        allocation = float(allocation_str) if allocation_str and allocation_str != 'nan' else 0
                    except (ValueError, KeyError, IndexError):
                        
                        try:
                            name_parts = str(row[mapping['name']]).strip().split('%')
                            if len(name_parts) > 1:
                                allocation = float(name_parts[1].strip().split()[0])
                            else:
                                allocation = 0
                        except (ValueError, IndexError):
                            allocation = 0
                    
                    
                    if account_name == 'M1_Finance':
                        try:
                            div_yield_str = str(row[mapping['div_yield']]).replace('%', '').strip()
                            div_yield_pct = float(div_yield_str) if div_yield_str and div_yield_str != 'nan' else 0
                            
                            annual_div_str = str(row[mapping['annual_div']]).replace('$', '').replace(',', '').strip()
                            annual_dividend = float(annual_div_str) if annual_div_str and annual_div_str != 'nan' else 0
                        except (ValueError, KeyError, IndexError):
                            div_yield = get_dividend_info(symbol)
                            div_yield_pct = div_yield * 100
                            annual_dividend = equity * (div_yield_pct / 100)
                    else:
                        div_yield = get_dividend_info(symbol)
                        div_yield_pct = div_yield * 100
                        annual_dividend = equity * (div_yield_pct / 100)
                    
                    total_portfolio_value += equity
                    total_dividend_income += annual_dividend
                    
                    
                    try:
                        allocation_str = str(row[mapping.get('allocation', -1)]).replace('%', '').strip() if mapping.get('allocation') is not None else '0'
                        allocation = float(allocation_str) if allocation_str and allocation_str != 'nan' else 0
                    except (IndexError, ValueError, KeyError):
                        allocation = 0
                        print(f"Warning: Could not read allocation for {symbol}, defaulting to 0")
                    
                    all_holdings.append({
                        'symbol': symbol,
                        'name': name,
                        'equity': equity,
                        'cost': cost,
                        'gain_loss': gain_loss,
                        'return_pct': (gain_loss / cost * 100) if cost != 0 else 0,
                        'dividend_yield': div_yield_pct,
                        'annual_dividend': annual_dividend,
                        'account': account_name,
                        'allocation': allocation
                    })
            except Exception as e:
                print(f"Error processing row {i} in {account_name}: {str(e)}")
                continue

    # Combine duplicate stocks
    combined_holdings = {}
    for holding in all_holdings:
        symbol = holding['symbol']
        if symbol not in combined_holdings:
            combined_holdings[symbol] = holding.copy()
        else:
            
            combined_holdings[symbol]['equity'] += holding['equity']
            combined_holdings[symbol]['cost'] += holding['cost']
            combined_holdings[symbol]['gain_loss'] += holding['gain_loss']
            combined_holdings[symbol]['return_pct'] = (
                (combined_holdings[symbol]['gain_loss'] / combined_holdings[symbol]['cost'] * 100)
                if combined_holdings[symbol]['cost'] != 0 else 0
            )
            
            if holding['account'] not in combined_holdings[symbol]['account']:
                combined_holdings[symbol]['account'] = f"{combined_holdings[symbol]['account']}, {holding['account']}"
    
    # Convert back to list
    all_holdings = list(combined_holdings.values())
    
    # Calculate total portfolio value
    total_portfolio_value = sum(holding['equity'] for holding in all_holdings)

    # Calculate allocations based on equity values
    for holding in all_holdings:
        holding['allocation'] = (holding['equity'] / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

    # Sort holdings by different metrics
    best_performers = sorted(all_holdings, key=lambda x: x['return_pct'], reverse=True)
    worst_performers = sorted(all_holdings, key=lambda x: x['return_pct'])
    largest_allocations = sorted(all_holdings, key=lambda x: x['allocation'], reverse=True)

    # Calculate total portfolio dividend yield
    total_dividend_income = sum(holding['annual_dividend'] for holding in all_holdings)
    portfolio_dividend_yield = (total_dividend_income / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

    # Print Portfolio Allocation
    print("\nPortfolio Allocation:")
    # Format the table header and data
    header = [
        "Symbol", "Name", "Allocation %", "Value ($)", "Yield (%)", "Annual Div ($)"
    ]
    
    # Print header
    print("-" * 100)
    print("{:<8}  {:<35}  {:>12}  {:>13}  {:>10}  {:>13}".format(*header))
    print("-" * 100)
    
    # Print holdings
    for holding in largest_allocations:
        # Get values
        symbol = holding['symbol']
        name = holding['name'][:35]  # Truncate name if too long
        allocation = holding['allocation']
        equity = holding['equity']
        div_yield = holding['dividend_yield']
        annual_div = holding['annual_dividend']
        
        # Print row with proper formatting
        print("{:<8}  {:<35}  {:>11.2f}%  ${:>11,.2f}  {:>9.2f}%  ${:>11,.2f}".format(
            symbol,
            name,
            allocation,
            equity,
            div_yield,
            annual_div
        ))
    
    # Print total
    print("-" * 100)
    print("{:<45}  {:>11.2f}%  ${:>11,.2f}  {:>9.2f}%  ${:>11,.2f}".format(
        "Total",
        100.00,
        total_portfolio_value,
        portfolio_dividend_yield,
        total_dividend_income
    ))

    # Print Best Performers
    print("\nBest Performing Stocks:")
    print("-" * 80)
    print(f"{'Symbol':<10} {'Name':<30} {'Return %':<15} {'Gain/Loss':<15}")
    print("-" * 80)
    for holding in best_performers[:5]:  # Top 5 performers
        print(f"{holding['symbol']:<10} {holding['name'][:28]:<30} {holding['return_pct']:,.2f}% ${holding['gain_loss']:,.2f}")

    # Print Worst Performers
    print("\nWorst Performing Stocks:")
    print("-" * 80)
    print(f"{'Symbol':<10} {'Name':<30} {'Return %':<15} {'Gain/Loss':<15}")
    print("-" * 80)
    for holding in worst_performers[:5]:  # Bottom 5 performers
        print(f"{holding['symbol']:<10} {holding['name'][:28]:<30} {holding['return_pct']:,.2f}% ${holding['gain_loss']:,.2f}")



def stock_analysis(ticker):
    if not ticker:
        return None
        
    # Clean the ticker
    ticker = ticker.strip().upper()
    
    try:
        print(f"\nAnalyzing {ticker}...")
        stock = yf.Ticker(ticker)
        
        # Get historical data first to validate ticker
        print("Getting historical data...")
        hist = stock.history(period='1y')
        if hist.empty:
            print(f"No historical data available for {ticker}")
            return None
            
        # Calculate price metrics from historical data
        current_price = hist['Close'].iloc[-1]
        week_52_high = hist['High'].max()
        week_52_low = hist['Low'].min()
        print(f"Current price: ${current_price:.2f}")
        
        # Get quarterly financials
        print("Getting financial data...")
        try:
            financials = stock.quarterly_financials
            if not financials.empty:
                # Calculate trailing 12m earnings
                net_income = financials.loc['Net Income'].head(4).sum()
                print(f"Net Income (TTM): ${net_income:,.2f}")
            else:
                net_income = None
        except:
            net_income = None
            
        # Get shares outstanding
        try:
            shares = stock.get_shares_full().iloc[-1]
            print(f"Shares Outstanding: {shares:,.0f}")
        except:
            try:
                # Fallback to fast info
                shares = stock.fast_info.shares_outstanding
                print(f"Shares Outstanding (fast): {shares:,.0f}")
            except:
                shares = None
        
        # Calculate market cap
        if shares is not None:
            market_cap = shares * current_price
        else:
            market_cap = 0
        print(f"Market Cap: ${market_cap:,.2f}")
        
        # Calculate PE ratio
        if net_income is not None and net_income > 0 and shares is not None:
            pe_ratio = (current_price * shares) / net_income
        else:
            pe_ratio = 0
        print(f"P/E Ratio: {pe_ratio:.2f}")
        
        # Get analyst estimates
        try:
            analysts = stock.analyst_price_target
            if not analysts.empty:
                mean_target = analysts['targetMeanPrice'].iloc[-1]
                forward_pe = mean_target / current_price if current_price > 0 else 0
            else:
                forward_pe = 0
        except:
            forward_pe = 0
        print(f"Forward P/E: {forward_pe:.2f}")
        
        # Calculate PEG using historical growth
        try:
            # Calculate 1-year return
            year_ago_price = hist['Close'].iloc[0]
            growth_rate = ((current_price / year_ago_price) - 1) * 100
            peg_ratio = pe_ratio / growth_rate if growth_rate > 0 and pe_ratio > 0 else 0
        except:
            peg_ratio = 0
        print(f"PEG Ratio: {peg_ratio:.2f}")
        
        # Calculate beta
        try:
            # Get market data (using SPY as proxy)
            spy = yf.download('^GSPC', start=hist.index[0], end=hist.index[-1], progress=False)['Close']
            # Calculate daily returns
            stock_returns = hist['Close'].pct_change()
            market_returns = spy.pct_change()
            # Calculate beta
            covariance = stock_returns.cov(market_returns)
            market_variance = market_returns.var()
            beta = covariance / market_variance
        except:
            beta = 0
        print(f"Beta: {beta:.2f}")
        
        # Return dictionary of results
        result = {
            'current_price': current_price,
            '52_week_high': week_52_high,
            '52_week_low': week_52_low,
            'market_cap': market_cap,
            'pe_ratio': pe_ratio,
            'forward_pe': forward_pe,
            'peg_ratio': peg_ratio,
            'beta': beta
        }
        
        print("Analysis complete!")
        return result
        
    except Exception as e:
        print(f"Error analyzing {ticker}: {str(e)}")
        return None
        print(f"Error analyzing {ticker}: {str(e)}")
        return None

def fire_calculator(retirement_age, annual_expenses, current_age, 
                   monthly_investment, monthly_cash_savings, current_cash_savings=0, portfolio_dividend_yield=0.02):
    """Calculate FIRE (Financial Independence, Retire Early) metrics.
    Returns a dictionary containing all the calculated values."""

    try:
        # Get current portfolio value from gs_reader
        current_portfolio, _ = gs_reader()
    except:
        # If there's an error reading the portfolio, start with 0
        current_portfolio = 0
    
    # Calculate current dividend income based on portfolio value and yield
    current_dividend_income = current_portfolio * portfolio_dividend_yield
    
    # Years until retirement
    years_until_retirement = retirement_age - current_age
    
    # Assume 7% average annual return on investments (conservative estimate)
    annual_investment_return_rate = 0.07
    
    # Assume 2% average return on cash savings
    annual_savings_return_rate = 0.02

    # Calculate future investment portfolio value
    future_portfolio_value = current_portfolio * (1 + annual_investment_return_rate) ** years_until_retirement
    
    # Calculate future cash savings value
    future_cash_savings = current_cash_savings * (1 + annual_savings_return_rate) ** years_until_retirement
    
    # Add impact of monthly contributions
    if years_until_retirement > 0:
        # For investments
        monthly_investment_rate = annual_investment_return_rate / 12
        num_months = years_until_retirement * 12
        future_monthly_investments = monthly_investment * (
            ((1 + monthly_investment_rate) ** num_months - 1) / monthly_investment_rate
        ) * (1 + monthly_investment_rate)
        
        # For cash savings
        monthly_savings_rate = annual_savings_return_rate / 12
        future_monthly_savings = monthly_cash_savings * (
            ((1 + monthly_savings_rate) ** num_months - 1) / monthly_savings_rate
        ) * (1 + monthly_savings_rate)
        
        future_portfolio_value += future_monthly_investments
        future_cash_savings += future_monthly_savings
    
    # Calculate total future value
    total_future_value = future_portfolio_value + future_cash_savings
    
    # Project dividend income at retirement
    projected_dividend_income = future_portfolio_value * portfolio_dividend_yield
    
    # Calculate safe withdrawal amount (4% rule)
    safe_withdrawal_amount = future_portfolio_value * 0.04
    
    # Calculate total annual retirement income
    total_retirement_income = safe_withdrawal_amount + projected_dividend_income
    
    # Calculate required portfolio based on annual expenses
    required_portfolio = annual_expenses * 25
    
    # Calculate any shortfall
    shortfall = max(0, required_portfolio - total_future_value)
    
    # Calculate additional monthly investment needed if there's a shortfall
    if shortfall > 0 and years_until_retirement > 0:
        additional_monthly_needed = (shortfall * (annual_investment_return_rate / 12)) / (
            ((1 + annual_investment_return_rate / 12) ** (years_until_retirement * 12)) - 1
        )
    else:
        additional_monthly_needed = 0
    
    return {
        "current_portfolio": current_portfolio,
        "current_cash_savings": current_cash_savings,
        "current_dividend_income": current_dividend_income,
        "future_portfolio_value": future_portfolio_value,
        "future_cash_savings": future_cash_savings,
        "total_future_value": total_future_value,
        "projected_dividend_income": projected_dividend_income,
        "safe_withdrawal_amount": safe_withdrawal_amount,
        "total_retirement_income": total_retirement_income,
        "required_portfolio": required_portfolio,
        "shortfall": shortfall,
        "additional_monthly_needed": additional_monthly_needed,
        "years_to_fire": years_until_retirement,
        "required_monthly_investment": monthly_investment + additional_monthly_needed
    }

def calculate_fair_value(ticker):
    """Calculate the fair value of a stock using the modified PEG ratio method."""
    try:
        stock = yf.Ticker(ticker)
        
        # Get required data using multiple fallback methods
        try:
            # Get current price from history
            hist = stock.history(period='1d')
            if hist.empty:
                return None, "No price data available"
            current_price = hist['Close'].iloc[-1]
            
            # Multiple methods to get P/E Ratio
            pe_ratio = None
            
            
            try:
                pe_ratio = stock.fast_info.trailing_pe
            except:
                pass
            
            
            if pe_ratio is None:
                try:
                    info = stock.info
                    pe_ratio = info.get('trailingPE') or info.get('forwardPE')
                except:
                    pass
            
            
            if pe_ratio is None:
                try:
                    financials = stock.financials
                    if not financials.empty and 'Basic EPS' in financials.index:
                        latest_eps = financials.loc['Basic EPS'].iloc[0]
                        if latest_eps > 0:  # Ensure positive EPS
                            pe_ratio = current_price / latest_eps
                except:
                    pass
            
            
            if pe_ratio is None:
                try:
                    quarterly = stock.quarterly_financials
                    if not quarterly.empty and 'Basic EPS' in quarterly.index:
                        ttm_eps = quarterly.loc['Basic EPS'].head(4).sum()  # TTM EPS
                        if ttm_eps > 0:  # Ensure positive EPS
                            pe_ratio = current_price / ttm_eps
                except:
                    pass
            
            if pe_ratio is None:
                return None, "Unable to calculate P/E ratio using any method"
            
            # Get EPS Growth Rate using multiple methods
            eps_growth = None
            
            
            try:
                financials = stock.financials
                if not financials.empty and 'Basic EPS' in financials.index:
                    eps_history = financials.loc['Basic EPS']
                    if len(eps_history) >= 2 and eps_history.iloc[-1] > 0:
                        eps_growth = ((eps_history.iloc[0] / eps_history.iloc[-1]) ** (1/len(eps_history)) - 1) * 100
            except:
                pass
            
            
            if eps_growth is None:
                try:
                    quarterly = stock.quarterly_financials
                    if not quarterly.empty and 'Basic EPS' in quarterly.index:
                        eps_quarterly = quarterly.loc['Basic EPS']
                        if len(eps_quarterly) >= 5:  # Need 5 quarters for YoY comparison
                            yoy_growth = (eps_quarterly.iloc[0] / eps_quarterly.iloc[4] - 1) * 100
                            eps_growth = yoy_growth
                except:
                    pass
            
           
            if eps_growth is None:
                try:
                    info = stock.info
                    eps_growth = (info.get('earningsGrowth', 0) or info.get('earningsQuarterlyGrowth', 0)) * 100
                except:
                    pass
            
            if eps_growth is None:
                eps_growth = 0  # Default to 0 if no growth data available
            
            # Get Dividend Yield using multiple methods
            div_yield = 0  # Default to 0
            
            
            try:
                div_yield = get_dividend_info(ticker) * 100
            except:
                pass
            
            
            if div_yield == 0:
                try:
                    info = stock.info
                    div_yield = (info.get('dividendYield', 0) or info.get('trailingAnnualDividendYield', 0)) * 100
                except:
                    pass
            
            # Calculate PEG Ratio with safeguards
            if eps_growth <= 0:
                peg_ratio = pe_ratio  # Use P/E as PEG if no growth
            else:
                peg_ratio = pe_ratio / eps_growth
            
            # Calculate Fair Value
            fair_value = (pe_ratio / peg_ratio) * (eps_growth + div_yield)
            
            # Sanity check on fair value
            if fair_value <= 0:
                return None, "Calculated fair value is negative"
            if fair_value > current_price * 5:
                return None, "Calculated fair value appears unreasonably high"
            
            return {
                'fair_value': fair_value,
                'current_price': current_price,
                'pe_ratio': pe_ratio,
                'peg_ratio': peg_ratio,
                'eps_growth': eps_growth,
                'dividend_yield': div_yield,
                'valuation_ratio': current_price / fair_value if fair_value > 0 else None
            }, None
            
        except Exception as e:
            return None, f"Error calculating metrics: {str(e)}"
            
    except Exception as e:
        return None, f"Error accessing stock data: {str(e)}"

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/portfolio')
def get_portfolio():
    try:
        total_equity, dataframes = gs_reader()
        
        # Get portfolio analysis data
        all_holdings = []
        for df in dataframes:
            for i in range(1, len(df)):
                try:
                    row = df.iloc[i]
                    if len(row) >= 8 and isinstance(row[0], str) and row[0].strip():
                        equity = float(row[5].replace('$', '').replace(',', '')) if isinstance(row[5], str) else 0
                        all_holdings.append({
                            'symbol': row[0],
                            'name': row[1],
                            'equity': equity,
                            'allocation': (equity / total_equity * 100) if total_equity > 0 else 0
                        })
                except (ValueError, IndexError) as e:
                    print(f"Error processing row {i}: {str(e)}")
                    continue
        
        if not all_holdings:
            return jsonify({'error': 'No portfolio data could be processed'}), 500
        
        # Sort by allocation
        all_holdings.sort(key=lambda x: x['allocation'], reverse=True)
        
        return jsonify({
            'total_equity': total_equity,
            'allocations': all_holdings
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        print(f"Error in get_portfolio: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze_stock/<ticker>')
def analyze_stock(ticker):
    try:
        if not ticker:
            return jsonify({'error': 'No ticker symbol provided'}), 400
            
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            return jsonify({'error': f'No data found for ticker {ticker}'}), 404
        
        return jsonify({
            'company_name': info.get('longName', 'N/A'),
            'current_price': info.get('currentPrice', 0),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh', 0),
            'fifty_two_week_low': info.get('fiftyTwoWeekLow', 0)
        })
    except Exception as e:
        print(f"Error analyzing stock {ticker}: {str(e)}")
        return jsonify({'error': f'Error analyzing stock {ticker}: {str(e)}'}), 500

@app.route('/api/calculate_fire', methods=['POST'])
def calculate_fire():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        required_fields = ['retirement_age', 'desired_retirement_income', 'current_age', 
                         'current_income', 'monthly_investment', 'monthly_cash_savings']
        
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
            
        result = fire_calculator(
            retirement_age=data['retirement_age'],
            desired_retirement_income=data['desired_retirement_income'],
            current_age=data['current_age'],
            current_income=data['current_income'],
            monthly_investment=data['monthly_investment'],
            monthly_cash_savings=data['monthly_cash_savings'],
            current_cash_savings=data.get('current_cash_savings', 0)
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': f'Invalid input: {str(e)}'}), 400
    except Exception as e:
        print(f"Error calculating FIRE: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
