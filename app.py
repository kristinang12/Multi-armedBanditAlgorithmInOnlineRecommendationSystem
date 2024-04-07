from flask import Flask, render_template, request, session
import psycopg2
import random
from flask import redirect, url_for
import uuid

app = Flask(__name__)

app.secret_key = "rl"  # Set a secret key for the session

# Connect to the PostgreSQL database
conn = psycopg2.connect(
    dbname="LRRecommendationSystem",
    user="postgres",
    password="mystika12",
    host="localhost",
    port="5432"
)

cur = conn.cursor()
    
def regretCalculation(arm_id):
    
    if arm_id is not None:
        cur.execute("SELECT average_reward FROM armsreward ORDER BY average_reward DESC LIMIT 1")
        optimal_reward = cur.fetchone()[0]
        
        cur.execute("SELECT average_reward FROM armsreward WHERE arm_id = %s", (arm_id,))
        actionSelected_reward = cur.fetchone()[0]

        regret = optimal_reward - actionSelected_reward
        cur.execute("INSERT INTO regretcalculation (selectedarm, optimalarmval, selectedprobval, regret) VALUES (%s, %s, %s, %s)", (arm_id, optimal_reward, actionSelected_reward, regret))
    
    conn.commit()
    
# Update reward calculation
def rewardCalculation(arm_id):
    cur.execute("SELECT alpha, beta, average_reward FROM armsreward WHERE arm_id = %s", (arm_id,))
    row = cur.fetchone()
    
    if row is not None:
        alpha, beta, average_reward = row
        cur.execute("INSERT INTO rewardcalculation (arm_id, alpha, beta, average_reward) VALUES (%s, %s, %s, %s)", (arm_id, alpha, beta, average_reward))
        conn.commit()
        
# Update reward
def updateReward(arm_id):
    cur.execute("SELECT alpha, beta, average_reward FROM armsreward WHERE arm_id = %s", (arm_id,))
    row = cur.fetchone()
    
    if row is not None:
        alpha, beta, average_reward = row
        beta -= 1
        alpha += 1
        average_reward = alpha / (beta+alpha) if alpha > 0 else 0
        cur.execute("UPDATE armsreward SET alpha = %s, beta = %s, average_reward = %s WHERE arm_id = %s", (alpha, beta, average_reward, arm_id))
        conn.commit()

def observereward(arm_id):
    
    cur.execute("SELECT id FROM rewardcalculation ORDER BY id DESC")
    id = cur.fetchone()[0] if cur.rowcount > 0 else None
    if arm_id is not None:
        cur.execute("UPDATE rewardcalculation SET reward = reward + 1 WHERE id= %s", (id,))
        conn.commit()
        
def updateArmSelection(arm_id):

    cur.execute("SELECT alpha, beta, average_reward FROM armsreward WHERE arm_id = %s", (arm_id,))
    row = cur.fetchone()
    
    if row:
        alpha, beta, average_reward = row

        beta += 1
        
        average_reward = alpha / (beta+alpha) if alpha > 0 else 0
        
        cur.execute("UPDATE armsreward SET alpha = %s, beta= %s, average_reward = %s  WHERE arm_id = %s", (alpha, beta, average_reward, arm_id))
        
    conn.commit()

def select_arm():
    
    num_arms = 10
    sampled_probs = []

    for arm_id in range(1, num_arms + 1):
        cur.execute("SELECT alpha, beta FROM armsreward WHERE arm_id = %s", (arm_id,))
        row = cur.fetchone()

        if row is not None:
            alpha, beta = row
            # Sample success probability from the posterior Beta distribution
            sampled_prob = random.betavariate(alpha, beta)
            sampled_probs.append((arm_id, sampled_prob))

    if sampled_probs:
        # Select an arm based on the expected rewards
        arm_id = max(sampled_probs, key=lambda x: x[1])[0]
        
        return arm_id
    
    
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'recommended_lm_titles' not in session:
        session['recommended_lm_titles'] = []

    recommended_lm_titles = session['recommended_lm_titles']
    search_recommendation = []
    no_results_message = ""
    show_results_label = False

    if 'arm_id' not in session:
        session['arm_id'] = select_arm()

    arm_id = session['arm_id']

    if 'updated_db' not in session or not session['updated_db']:  # Check if database update is needed
        # Retrieve the learning material titles for the selected arm
        cur.execute("SELECT lm_title FROM arms WHERE arm_id = %s", (arm_id,))
        rows = cur.fetchall()
        arm_recommendations = [row[0] for row in rows] if cur.rowcount > 0 else []

        recommended_lm_titles.extend(arm_recommendations)
        session['recommended_lm_titles'] = recommended_lm_titles

        session['updated_db'] = True  # Update the flag to indicate database has been updated

        # Update the database
        regretCalculation(arm_id)
        rewardCalculation(arm_id)
        updateArmSelection(arm_id)

    if request.method == 'POST':
        search_query = request.form['search_query']

        # Check if the search query is not empty
        if search_query.strip():
            # Retrieve all learning materials containing the search query in their title
            cur.execute(
                "SELECT lm_title FROM armsreward WHERE lower(lm_title) LIKE lower(%s) ORDER BY average_reward DESC LIMIT 1",
                ('%{}%'.format(search_query),))
            rows = cur.fetchall()
            search_results = [row[0] for row in rows] if cur.rowcount > 0 else []

            if not search_results:
                no_results_message = "No search results found. Try recommended learning material."
            else:
                show_results_label = True

            search_recommendation.extend(search_results)

    return render_template('index.html', recommended_lm_titles=recommended_lm_titles,
                           search_recommendation=search_recommendation, no_results_message=no_results_message,
                           show_results_label=show_results_label)


@app.route('/click_resultquery/<lm_result>', methods=['GET'])
def click_resultquery(lm_result):
    # Retrieve the arm_id of the clicked learning material
    cur.execute("SELECT arm_id FROM armsreward WHERE lm_title = %s", (lm_result,))
    row = cur.fetchone()
    id = row[0] if row else None
    
    # Update the armsreward table with the arm_id
        
    # Retrieve the description of the clicked learning material
    cur.execute("SELECT description FROM arms WHERE lm_title = %s", (lm_result,))
    row = cur.fetchone()
    description = row[0] if row else "Description not found"
    return render_template('material.html', description=description)

@app.route('/click_lm/<lm_title>', methods=['GET'])
def click_lm(lm_title):
    # Retrieve the arm_id of the clicked learning material
    cur.execute("SELECT arm_id FROM armsreward WHERE lm_title = %s", (lm_title,))
    row = cur.fetchone()
    id = row[0] if row else None
    
    # Update the armsreward table with the arm_id
    
    if (id):
        updateReward(id)
        observereward(id)
    
    # Retrieve the description of the clicked learning material
    cur.execute("SELECT description FROM arms WHERE lm_title = %s", (lm_title,))
    row = cur.fetchone()
    description = row[0] if row else "Description not found"
    return render_template('material.html', description=description)

if __name__ == '__main__':
    app.run(debug=True)
