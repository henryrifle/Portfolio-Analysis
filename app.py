import streamlit as st
import pandas as pd
from backend import gs_reader, portfolio_analysis, stock_analysis, fire_calculator, get_dividend_info, calculate_fair_value
import io
import sys
import altair as alt


st.set_page_config(page_title="Financial Planner", layout="wide")

def capture_output(func, *args):
    # Capture stdout to get the portfolio analysis text output
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    
    try:
        result = func(*args)
        output = new_stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    
    return output, result

def main():
    st.title("Financial Portfolio Dashboard")

    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Select a Page",
        ["Portfolio Overview", "FIRE Calculator", "Compound Interest Calculator", "Fair Value Calculator"]
    )

    if page == "Portfolio Overview":
        try:
            total_equity, dataframes = gs_reader()
            st.header("Portfolio Overview")
            
            # Create columns for portfolio values
            cols = st.columns(len(dataframes) + 1)
            
            # Show total portfolio value in first column
            with cols[0]:
                st.metric("Total Portfolio", f"${total_equity:,.2f}")
            
            # Show individual portfolio values
            for idx, (account_name, data) in enumerate(dataframes.items(), 1):
                with cols[idx]:
                    df = data['df']
                    mapping = data['mapping']
                    try:
                        if isinstance(mapping['equity'], int):
                            equity = df[mapping['equity']].iloc[-1].replace("$", "").replace(",", "")
                        else:
                            equity = df[mapping['equity']].iloc[-1].replace("$", "").replace(",", "")
                        equity_value = float(equity)
                        st.metric(account_name, f"${equity_value:,.2f}")
                    except Exception as e:
                        st.metric(account_name, "Error")

            
            st.subheader("Quick Stock Analysis")
            col1, col2 = st.columns([3, 1])
            with col1:
                ticker = st.text_input("Enter a stock ticker to analyze", key="portfolio_ticker")
            with col2:
                analyze_button = st.button("Analyze")
            
            if ticker and analyze_button:
                with st.spinner(f"Analyzing {ticker.upper()}..."):
                    stock_data = stock_analysis(ticker)
                    if stock_data:
                        metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
                        with metrics_col1:
                            st.metric("Current Price", f"${stock_data['current_price']:.2f}")
                            st.metric("52-Week High", f"${stock_data['52_week_high']:.2f}")
                        with metrics_col2:
                            st.metric("Market Cap", f"${stock_data['market_cap']:,.0f}")
                            st.metric("52-Week Low", f"${stock_data['52_week_low']:.2f}")
                        with metrics_col3:
                            st.metric("P/E Ratio", f"{stock_data['pe_ratio']:.2f}")
                            try:
                                st.metric("Dividend Yield", f"{stock_data.get('dividend_yield', 0):.2%}")
                            except (KeyError, TypeError):
                                st.metric("Dividend Yield", "N/A")
                    else:
                        st.error(f"Could not fetch data for {ticker.upper()}. Please check the ticker symbol.")
            
            # Display portfolio analysis
            st.subheader("Portfolio Analysis")
            with st.spinner("Analyzing portfolio..."):
                # Display portfolio data directly from dataframes
                st.subheader("Portfolio Allocation")
                
                # Add account selection
                accounts = list(dataframes.keys())
                selected_account = st.selectbox("Select Account", ["All Accounts"] + accounts)
                
                if selected_account == "All Accounts":
                    # Combine data from all accounts
                    all_data = []
                    for account, data in dataframes.items():
                        df = data['df']
                        mapping = data['mapping']
                        
                        # Process each row except the last (total) row
                        for i in range(len(df) - 1):
                            row = df.iloc[i]
                            if pd.notna(row[mapping['symbol']]):
                                try:
                                    # Clean and convert all numeric values first
                                    symbol = str(row[mapping['symbol']]).strip()
                                    name = str(row[mapping['name']]).strip()
                                    equity = float(str(row[mapping['equity']]).replace('$', '').replace(',', ''))
                                    cost = float(str(row[mapping['cost']]).replace('$', '').replace(',', ''))
                                    gl = float(str(row[mapping['gl']]).replace('$', '').replace(',', ''))
                                    allocation = float(str(row[mapping['allocation']]).replace('%', '').strip() or 0)
                                    gl_percent = ((equity - cost) / cost * 100) if cost != 0 else 0
                                    
                                    # Get dividend information
                                    div_yield = get_dividend_info(symbol) * 100
                                    annual_div = equity * (div_yield / 100)
                                    
                                    all_data.append({
                                        'Symbol': symbol,
                                        'Name': name,
                                        'Total Equity': f"${equity:,.2f}",
                                        'Allocation': f"{allocation:.2f}%",
                                        'Total Gain/Loss': f"${gl:,.2f}",
                                        '% Gain/Loss': f"{gl_percent:.2f}%",
                                        'Dividend Yield': f"{div_yield:.2f}%",
                                        'Annual Dividend': f"${annual_div:.2f}"
                                    })
                                except (ValueError, KeyError) as e:
                                    print(f"Error processing row for {symbol if 'symbol' in locals() else 'unknown'}: {str(e)}")
                                    continue
                    
                    if all_data:
                        df_display = pd.DataFrame(all_data)
                        st.dataframe(df_display, use_container_width=True)
                        
                        # Show performance and dividend analysis
                        show_analysis(df_display)
                else:
                    # Display data for selected account
                    data = dataframes[selected_account]
                    df = data['df']
                    mapping = data['mapping']
                    
                    display_data = []
                    for i in range(len(df) - 1):
                        row = df.iloc[i]
                        if pd.notna(row[mapping['symbol']]):
                            try:
                                # Clean and convert all numeric values first
                                symbol = str(row[mapping['symbol']]).strip()
                                name = str(row[mapping['name']]).strip()
                                equity = float(str(row[mapping['equity']]).replace('$', '').replace(',', ''))
                                cost = float(str(row[mapping['cost']]).replace('$', '').replace(',', ''))
                                gl = float(str(row[mapping['gl']]).replace('$', '').replace(',', ''))
                                allocation = float(str(row[mapping['allocation']]).replace('%', '').strip() or 0)
                                gl_percent = ((equity - cost) / cost * 100) if cost != 0 else 0
                                
                                # Get dividend information
                                div_yield = get_dividend_info(symbol) * 100
                                annual_div = equity * (div_yield / 100)
                                
                                display_data.append({
                                    'Symbol': symbol,
                                    'Name': name,
                                    'Total Equity': f"${equity:,.2f}",
                                    'Allocation': f"{allocation:.2f}%",
                                    'Total Gain/Loss': f"${gl:,.2f}",
                                    '% Gain/Loss': f"{gl_percent:.2f}%",
                                    'Dividend Yield': f"{div_yield:.2f}%",
                                    'Annual Dividend': f"${annual_div:.2f}"
                                })
                            except (ValueError, KeyError) as e:
                                print(f"Error processing row for {symbol if 'symbol' in locals() else 'unknown'}: {str(e)}")
                                continue
                    
                    if display_data:
                        df_display = pd.DataFrame(display_data)
                        st.dataframe(df_display, use_container_width=True)
                        
                        # Show performance and dividend analysis
                        show_analysis(df_display)

        except Exception as e:
            st.error(f"Error loading portfolio data: {str(e)}")

    elif page == "FIRE Calculator":
        st.header("FIRE Calculator")
        
        # Create tabs for different sections
        tab1, tab2 = st.tabs(["Calculator", "Advanced Settings"])
        
        with tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Personal Information")
                current_age = st.number_input("Current Age", min_value=18, max_value=100, value=30)
                retirement_age = st.number_input("Desired Retirement Age", min_value=current_age, max_value=100, value=65)
                life_expectancy = st.number_input("Life Expectancy", min_value=retirement_age, max_value=120, value=90)
                
                st.subheader("Current Finances")
                annual_expenses = st.number_input("Current Annual Expenses ($)", min_value=0, value=40000)
                monthly_investment = st.number_input("Monthly Investment ($)", min_value=0, value=500)
                monthly_cash_savings = st.number_input("Monthly Cash Savings ($)", min_value=0, value=200)
                current_cash_savings = st.number_input("Current Cash Savings ($)", min_value=0, value=0)
                
            with col2:
                st.subheader("Retirement Assumptions")
                inflation_rate = st.slider("Expected Inflation Rate (%)", min_value=0.0, max_value=10.0, value=3.0, step=0.1)
                investment_return = st.slider("Expected Investment Return (%)", min_value=0.0, max_value=15.0, value=7.0, step=0.1)
                withdrawal_rate = st.slider("Safe Withdrawal Rate (%)", min_value=2.0, max_value=6.0, value=4.0, step=0.1)
                retirement_expenses_modifier = st.slider("Retirement Expenses Modifier (%)", 
                                                       min_value=50, max_value=150, value=100, 
                                                       help="Adjust expected retirement expenses as a percentage of current expenses")
                
                st.subheader("Income Sources")
                social_security = st.number_input("Expected Monthly Social Security ($)", min_value=0, value=2000)
                pension = st.number_input("Expected Monthly Pension ($)", min_value=0, value=0)
                portfolio_dividend_yield = st.number_input("Expected Portfolio Dividend Yield (%)", 
                                                         min_value=0.0, max_value=10.0, value=2.0, step=0.1)

        with tab2:
            st.subheader("Advanced Settings")
            col1, col2 = st.columns(2)
            
            with col1:
                include_social_security = st.checkbox("Include Social Security", value=True)
                include_pension = st.checkbox("Include Pension", value=True)
                account_for_inflation = st.checkbox("Account for Inflation", value=True)
            
            with col2:
                tax_rate = st.slider("Expected Retirement Tax Rate (%)", min_value=0, max_value=40, value=15)
                market_crash_scenario = st.checkbox("Include Market Crash Scenario", value=False)
                if market_crash_scenario:
                    crash_impact = st.slider("Market Crash Impact (%)", min_value=10, max_value=50, value=30)

        if st.button("Calculate FIRE"):
            try:
                # Adjust annual expenses for retirement
                retirement_annual_expenses = annual_expenses * (retirement_expenses_modifier / 100)
                
                # Calculate additional retirement income
                monthly_retirement_income = 0
                if include_social_security:
                    monthly_retirement_income += social_security
                if include_pension:
                    monthly_retirement_income += pension
                annual_retirement_income = monthly_retirement_income * 12
                
                # Calculate required retirement savings
                net_annual_expenses = retirement_annual_expenses - annual_retirement_income
                required_portfolio = (net_annual_expenses / (withdrawal_rate / 100))
                
                # Calculate current trajectory
                results = fire_calculator(
                    retirement_age, net_annual_expenses, current_age,
                    monthly_investment, monthly_cash_savings,
                    current_cash_savings, portfolio_dividend_yield / 100
                )
                
                # Display results in an organized layout
                st.subheader("FIRE Analysis Results")
                
                # Create three columns for different metrics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("### Current Status")
                    st.metric("Investment Portfolio", f"${results['current_portfolio']:,.2f}")
                    st.metric("Cash Savings", f"${results['current_cash_savings']:,.2f}")
                    st.metric("Current Annual Expenses", f"${annual_expenses:,.2f}")
                    st.metric("Years to FIRE", f"{results['years_to_fire']:.1f} years")
                
                with col2:
                    st.markdown("### Retirement Needs")
                    st.metric("FIRE Number", f"${required_portfolio:,.2f}")
                    st.metric("Annual Expenses in Retirement", f"${retirement_annual_expenses:,.2f}")
                    st.metric("Monthly Investment Needed", f"${results['required_monthly_investment']:,.2f}")
                    shortfall = max(0, required_portfolio - results['total_future_value'])
                    st.metric("Projected Shortfall", f"${shortfall:,.2f}")
                
                with col3:
                    st.markdown("### Retirement Income")
                    st.metric("Portfolio Dividend Income", f"${results['projected_dividend_income']:,.2f}/year")
                    st.metric("Social Security", f"${social_security * 12:,.2f}/year" if include_social_security else "Not Included")
                    st.metric("Pension Income", f"${pension * 12:,.2f}/year" if include_pension else "Not Included")
                    total_retirement_income = results['projected_dividend_income'] + (annual_retirement_income if include_social_security or include_pension else 0)
                    st.metric("Total Projected Income", f"${total_retirement_income:,.2f}/year")
                
                # Show additional analysis
                st.subheader("Detailed Analysis")
                
                # Calculate years of retirement coverage
                retirement_years = life_expectancy - retirement_age
                portfolio_depletion_rate = (net_annual_expenses - results['projected_dividend_income']) / results['total_future_value']
                years_covered = 1 / portfolio_depletion_rate if portfolio_depletion_rate > 0 else float('inf')
                
                st.write(f"""
                - You plan to retire in {results['years_to_fire']:.1f} years at age {retirement_age}
                - Your portfolio needs to last {retirement_years} years (until age {life_expectancy})
                - At current rates, your portfolio will cover {min(years_covered, retirement_years):.1f} years of retirement
                - Your monthly investment needs to be ${results['required_monthly_investment']:,.2f} to reach your FIRE goal
                """)
                
                if market_crash_scenario:
                    crash_portfolio = results['total_future_value'] * (1 - crash_impact/100)
                    st.warning(f"""
                    In a market crash scenario ({crash_impact}% drop):
                    - Your portfolio would drop to ${crash_portfolio:,.2f}
                    - You would need an additional ${required_portfolio - crash_portfolio:,.2f} to maintain your FIRE goal
                    """)
                
            except Exception as e:
                st.error(f"Error calculating FIRE metrics: {str(e)}")

    elif page == "Compound Interest Calculator":
        st.header("Compound Interest Calculator")
        
        # Try to get current portfolio value and dividend info
        try:
            current_portfolio_value, dataframes = gs_reader()
            has_portfolio_data = True
            
            # Calculate current dividend information
            current_dividend_total = 0
            for account_name, data in dataframes.items():
                df = data['df']
                mapping = data['mapping']
                
                # Skip the last row (totals)
                for i in range(len(df) - 1):
                    try:
                        row = df.iloc[i]
                        if pd.notna(row[mapping['symbol']]):
                            symbol = str(row[mapping['symbol']]).strip()
                            equity = float(str(row[mapping['equity']]).replace('$', '').replace(',', ''))
                            
                            # Get dividend yield for the symbol
                            div_yield = get_dividend_info(symbol)
                            annual_div = equity * div_yield
                            current_dividend_total += annual_div
                    except Exception as e:
                        continue
            
            current_dividend_yield = (current_dividend_total / current_portfolio_value * 100) if current_portfolio_value > 0 else 0
            
        except Exception as e:
            current_portfolio_value = 0
            current_dividend_total = 0
            current_dividend_yield = 0
            has_portfolio_data = False
            st.warning("Unable to load current portfolio data. Starting with $0.")
        
        # Create tabs for input options
        tab1, tab2 = st.tabs(["Calculator", "Portfolio Settings"])
        
        with tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Initial Investment")
                
                # Option to use current portfolio
                if has_portfolio_data:
                    use_current_portfolio = st.checkbox("Use Current Portfolio Value", value=True)
                    if use_current_portfolio:
                        st.info(f"Using current portfolio value: ${current_portfolio_value:,.2f}")
                        initial_amount = current_portfolio_value
                    else:
                        initial_amount = st.number_input("Initial Investment ($)", 
                                                       min_value=0.0, 
                                                       value=10000.0, 
                                                       step=1000.0)
                else:
                    initial_amount = st.number_input("Initial Investment ($)", 
                                                   min_value=0.0, 
                                                   value=10000.0, 
                                                   step=1000.0)
                
                monthly_contribution = st.number_input("Monthly Contribution ($)", 
                                                     min_value=0.0, 
                                                     value=500.0, 
                                                     step=100.0)
                investment_period = st.number_input("Investment Period (Years)", 
                                                  min_value=1, 
                                                  value=10)
            
            with col2:
                st.subheader("Return Rates")
                annual_return = st.slider("Expected Annual Return (%)", 
                                        min_value=0.0, 
                                        max_value=15.0, 
                                        value=7.0, 
                                        step=0.1)
                inflation_rate = st.slider("Expected Inflation Rate (%)", 
                                         min_value=0.0, 
                                         max_value=10.0, 
                                         value=3.0, 
                                         step=0.1)
                
                # If portfolio data is available, show current dividend yield
                if has_portfolio_data:
                    try:
                        current_dividend_total = sum(
                            float(str(row[data['mapping']['annual_div']]).replace('$', '').replace(',', ''))
                            for _, data in dataframes.items()
                            for _, row in data['df'].iterrows()
                            if pd.notna(row[data['mapping']['annual_div']])
                        )
                        current_dividend_yield = (current_dividend_total / current_portfolio_value * 100) if current_portfolio_value > 0 else 0
                        st.info(f"Current Portfolio Dividend Yield: {current_dividend_yield:.2f}%")
                        dividend_yield = st.slider("Expected Dividend Yield (%)", 
                                                min_value=0.0, 
                                                max_value=10.0, 
                                                value=current_dividend_yield, 
                                                step=0.1)
                    except:
                        dividend_yield = st.slider("Expected Dividend Yield (%)", 
                                                min_value=0.0, 
                                                max_value=10.0, 
                                                value=2.0, 
                                                step=0.1)
                else:
                    dividend_yield = st.slider("Expected Dividend Yield (%)", 
                                            min_value=0.0, 
                                            max_value=10.0, 
                                            value=2.0, 
                                            step=0.1)
                
                reinvest_dividends = st.checkbox("Reinvest Dividends", value=True)
        
        with tab2:
            st.subheader("Portfolio Details")
            if has_portfolio_data:
                # Show current portfolio breakdown
                st.write("Current Portfolio Allocation")
                
                # Create a summary DataFrame
                portfolio_summary = []
                for account_name, data in dataframes.items():
                    df = data['df']
                    mapping = data['mapping']
                    try:
                        equity = float(str(df[mapping['equity']].iloc[-1]).replace('$', '').replace(',', ''))
                        allocation = (equity / current_portfolio_value * 100) if current_portfolio_value > 0 else 0
                        portfolio_summary.append({
                            'Account': account_name,
                            'Value': f"${equity:,.2f}",
                            'Allocation': f"{allocation:.1f}%"
                        })
                    except:
                        continue
                
                if portfolio_summary:
                    st.table(pd.DataFrame(portfolio_summary))
                
                # Show current dividend information
                st.write("Current Dividend Information")
                try:
                    st.metric("Annual Dividend Income", 
                             f"${current_dividend_total:,.2f}",
                             f"Yield: {current_dividend_yield:.2f}%")
                except:
                    st.warning("Unable to calculate current dividend information")
            else:
                st.warning("No portfolio data available")
        
        if st.button("Calculate Growth"):
            # Calculate compound interest with monthly contributions
            nominal_values = []
            real_values = []
            dividend_income = []
            years = list(range(investment_period + 1))
            
            # Monthly rate calculations
            monthly_rate = annual_return / 12 / 100
            monthly_inflation = inflation_rate / 12 / 100
            monthly_dividend = dividend_yield / 12 / 100
            
            # Initial values
            current_nominal = initial_amount
            current_real = initial_amount
            
            nominal_values.append(current_nominal)
            real_values.append(current_real)
            dividend_income.append(0)
            
            for year in range(1, investment_period + 1):
                # Calculate year-end values
                for month in range(12):
                    # Add monthly contribution
                    current_nominal += monthly_contribution
                    
                    # Calculate monthly interest
                    interest = current_nominal * monthly_rate
                    current_nominal += interest
                    
                    # Calculate dividends
                    if reinvest_dividends:
                        dividends = current_nominal * monthly_dividend
                        current_nominal += dividends
                    
                    # Calculate real value (adjusted for inflation)
                    current_real = current_nominal / ((1 + monthly_inflation) ** (year * 12 + month))
                
                nominal_values.append(current_nominal)
                real_values.append(current_real)
                annual_dividend = current_nominal * dividend_yield / 100
                dividend_income.append(annual_dividend)
            
            # Create DataFrame for plotting
            df = pd.DataFrame({
                'Year': years,
                'Nominal Value': nominal_values,
                'Real Value': real_values,
                'Annual Dividend Income': dividend_income
            })
            
            # Display results
            st.subheader("Investment Growth Projection")
            
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Final Portfolio Value", f"${nominal_values[-1]:,.2f}")
                st.metric("Total Contributions", f"${(initial_amount + monthly_contribution * 12 * investment_period):,.2f}")
            
            with col2:
                st.metric("Real (Inflation-Adjusted) Value", f"${real_values[-1]:,.2f}")
                st.metric("Investment Growth", f"${(nominal_values[-1] - initial_amount - monthly_contribution * 12 * investment_period):,.2f}")
            
            with col3:
                st.metric("Final Annual Dividend Income", f"${dividend_income[-1]:,.2f}")
                roi = ((nominal_values[-1] / (initial_amount + monthly_contribution * 12 * investment_period)) - 1) * 100
                st.metric("Return on Investment", f"{roi:.1f}%")
            
            # Create and display the growth chart
            st.subheader("Portfolio Growth Over Time")
            chart_data = pd.melt(df, id_vars=['Year'], value_vars=['Nominal Value', 'Real Value', 'Annual Dividend Income'])
            
            chart = alt.Chart(chart_data).mark_line().encode(
                x=alt.X('Year:Q', title='Year'),
                y=alt.Y('value:Q', title='Value ($)'),
                color=alt.Color('variable:N', title='Metric')
            ).properties(
                height=400
            )
            
            st.altair_chart(chart, use_container_width=True)
            
            # Display year-by-year breakdown
            st.subheader("Year-by-Year Breakdown")
            
            # Format DataFrame for display
            display_df = df.copy()
            display_df['Nominal Value'] = display_df['Nominal Value'].map('${:,.2f}'.format)
            display_df['Real Value'] = display_df['Real Value'].map('${:,.2f}'.format)
            display_df['Annual Dividend Income'] = display_df['Annual Dividend Income'].map('${:,.2f}'.format)
            
            st.dataframe(display_df, use_container_width=True)
            
            # Additional insights
            st.subheader("Investment Insights")
            total_contributions = initial_amount + monthly_contribution * 12 * investment_period
            total_growth = nominal_values[-1] - total_contributions
            growth_percentage = (total_growth / total_contributions) * 100
            
            
            insights_text = f"""
            Investment Growth Summary:
            - Starting Value: ${initial_amount:,.2f}
            - Monthly Contribution: ${monthly_contribution:,.2f}
            - Final Value after {investment_period} years: ${nominal_values[-1]:,.2f}
            - Total Contributions: ${total_contributions:,.2f}
            - Total Growth: ${total_growth:,.2f} ({growth_percentage:.1f}% return)
            - Inflation-Adjusted Final Value: ${real_values[-1]:,.2f}
            - Final Year Dividend Income: ${dividend_income[-1]:,.2f}
            """
            
            st.write(insights_text)
            
            # Add detailed dividend analysis
            st.subheader("Dividend Analysis")
            if has_portfolio_data:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        "Current Annual Dividend Income",
                        f"${current_dividend_total:,.2f}",
                        f"Yield: {current_dividend_yield:.2f}%"
                    )
                with col2:
                    st.metric(
                        "Projected Annual Dividend Income",
                        f"${dividend_income[-1]:,.2f}",
                        f"Yield: {dividend_yield:.2f}%"
                    )
                
                # Show dividend growth
                dividend_growth = ((dividend_income[-1] / current_dividend_total) - 1) * 100 if current_dividend_total > 0 else 0
                st.metric(
                    "Dividend Growth",
                    f"{dividend_growth:,.1f}%",
                    f"${dividend_income[-1] - current_dividend_total:,.2f} increase"
                )
            else:
                st.metric(
                    "Projected Annual Dividend Income",
                    f"${dividend_income[-1]:,.2f}",
                    f"Yield: {dividend_yield:.2f}%"
                )
            
            # Add a dividend growth chart
            st.subheader("Dividend Income Projection")
            dividend_df = pd.DataFrame({
                'Year': years,
                'Annual Dividend Income': dividend_income
            })
            
            dividend_chart = alt.Chart(dividend_df).mark_area(
                opacity=0.4,
                color='green'
            ).encode(
                x=alt.X('Year:Q', title='Year'),
                y=alt.Y('Annual Dividend Income:Q', title='Dividend Income ($)')
            ).properties(
                height=300,
                title='Projected Dividend Income Growth'
            )
            
            st.altair_chart(dividend_chart, use_container_width=True)

    elif page == "Fair Value Calculator":
        st.header("Stock Fair Value Calculator")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Input for stock ticker
            ticker = st.text_input("Enter Stock Ticker", "").upper()
            
            if ticker:
                result, error = calculate_fair_value(ticker)
                
                if error:
                    st.error(error)
                elif result:
                    # Display results
                    st.subheader("Valuation Analysis")
                    
                    # Format the percentage difference
                    pct_diff = ((result['fair_value'] / result['current_price'] - 1) * 100)
                    pct_diff_formatted = f"{pct_diff:,.1f}%" if abs(pct_diff) < 1000 else f"{pct_diff/100:,.1f}x"
                    
                    # Create metrics display with adjusted column widths
                    col1, col2, col3 = st.columns([1.2, 1, 1.5])
                    
                    with col1:
                        st.metric(
                            "Fair Value",
                            f"${result['fair_value']:,.2f}",
                            pct_diff_formatted + " from current"
                        )
                        
                    with col2:
                        st.metric(
                            "Current Price",
                            f"${result['current_price']:,.2f}"
                        )
                        
                    with col3:
                        
                        if result['valuation_ratio'] > 1.1:
                            status = "Over"
                        elif result['valuation_ratio'] < 0.9:
                            status = "Under"
                        else:
                            status = "Fair"
                        
                        # Format the premium/discount percentage
                        premium_pct = ((result['valuation_ratio'] - 1) * 100)
                        premium_formatted = (
                            f"+{premium_pct:,.1f}%" if premium_pct > 0 
                            else f"{premium_pct:,.1f}%"
                        )
                        
                        st.metric(
                            "Valuation",
                            f"{status} Valued",
                            premium_formatted
                        )
                    
                    # Display detailed metrics with better formatting
                    st.subheader("Key Metrics")
                    metrics_df = pd.DataFrame({
                        'Metric': [
                            'P/E Ratio',
                            'PEG Ratio',
                            'EPS Growth Rate',
                            'Dividend Yield'
                        ],
                        'Value': [
                            f"{result['pe_ratio']:,.2f}",
                            f"{result['peg_ratio']:,.2f}",
                            f"{result['eps_growth']:,.1f}%",
                            f"{result['dividend_yield']:,.2f}%"
                        ]
                    })
                    st.table(metrics_df)
                    
                    
                    st.subheader("Interpretation")
                    premium = (result['valuation_ratio'] - 1) * 100
                    premium_text = (
                        f"{premium:,.1f}% premium" if premium > 0 
                        else f"{abs(premium):,.1f}% discount"
                    )
                    
                    interpretation = f"""
                    Based on the analysis:
                    - The stock's fair value is ${result['fair_value']:,.2f}
                    - Currently trading at ${result['current_price']:,.2f}
                    - The stock appears to be trading at a {premium_text} to its fair value
                    - This calculation considers:
                        * P/E Ratio of {result['pe_ratio']:,.2f}
                        * PEG Ratio of {result['peg_ratio']:,.2f}
                        * EPS Growth Rate of {result['eps_growth']:,.1f}%
                        * Dividend Yield of {result['dividend_yield']:,.2f}%
                    """
                    st.write(interpretation)
                    
        with col2:
            st.subheader("About Fair Value")
            st.write("""
            This calculator uses a modified PEG ratio method to estimate fair value:
            
            Fair Value = (P/E Ratio / PEG Ratio) × (EPS Growth + Dividend Yield)
            
            The formula considers:
            - P/E Ratio
            - Growth Rate
            - Dividend Yield
            - PEG Ratio
            
            A stock is considered:
            - Undervalued: < 90% of fair value
            - Fair Value: 90-110% of fair value
            - Overvalued: > 110% of fair value
            """)

def show_analysis(df_display):
    """Helper function to show performance and dividend analysis"""
    # Show top and worst performers
    st.subheader("Performance Analysis")
    col1, col2 = st.columns(2)
    
    # Convert % Gain/Loss to numeric for sorting
    df_display['% Gain/Loss_numeric'] = df_display['% Gain/Loss'].str.rstrip('%').astype(float)
    
    with col1:
        st.write("Top 5 Performers")
        top_performers = df_display.nlargest(5, '% Gain/Loss_numeric')[
            ['Symbol', 'Name', '% Gain/Loss', 'Total Gain/Loss']
        ]
        st.dataframe(top_performers, use_container_width=True)
        
    with col2:
        st.write("Bottom 5 Performers")
        bottom_performers = df_display.nsmallest(5, '% Gain/Loss_numeric')[
            ['Symbol', 'Name', '% Gain/Loss', 'Total Gain/Loss']
        ]
        st.dataframe(bottom_performers, use_container_width=True)
    
    # Show dividend analysis
    st.subheader("Dividend Analysis")
    col1, col2 = st.columns(2)
    
    # Convert dividend yield to numeric for sorting
    df_display['Dividend Yield_numeric'] = df_display['Dividend Yield'].str.rstrip('%').astype(float)
    
    with col1:
        st.write("Top 5 Dividend Yields")
        top_dividends = df_display.nlargest(5, 'Dividend Yield_numeric')[
            ['Symbol', 'Name', 'Dividend Yield', 'Annual Dividend']
        ]
        st.dataframe(top_dividends, use_container_width=True)
        
    with col2:
        # Calculate total portfolio dividend metrics
        total_equity = sum([float(str(x).replace('$', '').replace(',', '')) 
                         for x in df_display['Total Equity']])
        total_annual_div = sum([float(str(x).replace('$', '').replace(',', '')) 
                             for x in df_display['Annual Dividend']])
        portfolio_yield = (total_annual_div / total_equity * 100) if total_equity > 0 else 0
        
        st.metric("Portfolio Dividend Yield", f"{portfolio_yield:.2f}%")
        st.metric("Total Annual Dividend Income", f"${total_annual_div:,.2f}")

if __name__ == "__main__":
    main()
