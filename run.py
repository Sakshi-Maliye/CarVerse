from flask import Flask, request, redirect, url_for, session, render_template, render_template_string
import pandas as pd
import os
from app.database import load_data, save_event
from app.scoring import compute_broker_gamification

app = Flask(__name__, template_folder='app/templates')
app.secret_key = 'carverse_secret'

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_type = request.form.get('login_type')
        credential = request.form.get('credential', '').strip()
        events, employees, locations = load_data()
        
        if login_type == 'employee':
            user_row = employees[employees['name'] == credential]
            if not user_row.empty:
                session['user_type'] = 'employee'
                session['emp_id'] = int(user_row.iloc[0]['id'])
                session['loc_code'] = str(user_row.iloc[0]['loc_code'])
                return redirect(url_for('employee_dashboard'))
        
        elif login_type == 'branch':
            loc_row = locations[locations['loc_code'] == credential]
            if not loc_row.empty:
                session['user_type'] = 'branch'
                session['loc_code'] = str(loc_row.iloc[0]['loc_code'])
                session['location_name'] = str(loc_row.iloc[0]['location_name'])
                return redirect(url_for('branch_dashboard'))
    return render_template('login.html')

@app.route('/employee', methods=['GET', 'POST'])
def employee_dashboard():
    if session.get('user_type') != 'employee': return redirect(url_for('login'))
    
    events, employees, locations = load_data()
    scored_df = compute_broker_gamification(events, employees)
    me = scored_df[scored_df['emp_id'] == session['emp_id']].iloc[0]
    branch_team = scored_df[scored_df['loc_code'] == session['loc_code']].sort_values(by='xp', ascending=False).to_dict('records')
    
    return render_template('employee_dashboard.html', me=me, branch_team=branch_team)

@app.route('/branch')
def branch_dashboard():
    if session.get('user_type') != 'branch': return redirect(url_for('login'))
    
    events, employees, locations = load_data()
    scored_df = compute_broker_gamification(events, employees)
    
    branch_aggs = []
    for loc in locations['loc_code'].unique():
        loc_name = locations[locations['loc_code'] == loc].iloc[0]['location_name']
        loc_sub = scored_df[scored_df['loc_code'] == loc]
        avg_xp = loc_sub['xp'].mean() if not loc_sub.empty else 0
        avg_trust = loc_sub['trust_score'].mean() if not loc_sub.empty else 0
        branch_aggs.append({'loc_code': loc, 'location_name': loc_name, 'avg_xp': round(avg_xp, 1), 'avg_trust': round(avg_trust, 1)})
        
    branch_leaderboard = sorted(branch_aggs, key=lambda x: x['avg_trust'], reverse=True)
    return render_template('branch_dashboard.html', branch_leaderboard=branch_leaderboard)

@app.route('/action', methods=['POST'])
def handle_action():
    if 'user_type' not in session: return redirect(url_for('login'))
    action = request.form.get('action_type')
    if action == 'status_update':
        save_event(request.form.get('enquiry_no'), session['loc_code'], session['emp_id'], request.form.get('stage'))
    elif action == 'referral':
        save_event('REF_LOOP_BOUNTY', session['loc_code'], session['emp_id'], 'INVOICE')
    return redirect(url_for('employee_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)