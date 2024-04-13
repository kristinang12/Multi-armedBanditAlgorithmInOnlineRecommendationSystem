from flask import Flask, render_template, request, session
import psycopg2, random, os
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)


# Get the database URL from an environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

# Connect to the database using the DATABASE_URL environment variable
conn = psycopg2.connect(DATABASE_URL, sslmode='prefer')
cur = conn.cursor()

#postgres://lmrecommendationsystem_db_user:sg05UcW4YQS53HpmfmTeamDkqtXM8aIF@dpg-co95ksi0si5c7396oqu0-a/lmrecommendationsystem_db
#postgres://lmrecommendationsystem_db_user:sg05UcW4YQS53HpmfmTeamDkqtXM8aIF@dpg-co95ksi0si5c7396oqu0-a.ohio-postgres.render.com/lmrecommendationsystem_db
#sg05UcW4YQS53HpmfmTeamDkqtXM8aIF
#Host name/address: dpg-co95ksi0si5c7396oqu0-a.ohio-postgres.render.com
#Port: 5432
#Maintenance database: lmrecommendationsystem_db
#Username: lmrecommendationsystem_db_user
#Password: sg05UcW4YQS53HpmfmTeamDkqtXM8aIF


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

def select_arm(search_query=None):
    num_arms = 10
    sampled_probs = []

    # If there is a search query, prioritize arm selection based on the search query
    if search_query:
        cur.execute("SELECT arm_id, lm_title FROM armsreward WHERE lower(lm_title) LIKE lower(%s) ORDER BY average_reward DESC LIMIT 1",
                    ('%{}%'.format(search_query),))
        row = cur.fetchone()

        if row:
            arm_id, lm_title = row  # Unpack the row into arm_id and lm_title
            return arm_id
        
    # If there is no search query or no suitable arms found for the search query, fall back to Thompson Sampling
    if not sampled_probs:
        for arm_id in range(1, num_arms + 1):
            cur.execute("SELECT alpha, beta FROM armsreward WHERE arm_id = %s", (arm_id,))
            row = cur.fetchone()

            if row is not None:
                alpha, beta = row
                sampled_prob = random.betavariate(alpha, beta)
                sampled_probs.append((arm_id, sampled_prob))

    # Select an arm based on the expected rewards
    if sampled_probs:
        arm_id = max(sampled_probs, key=lambda x: x[1])[0]
        return arm_id

    # If no arm is selected, return a default recommendation
    return 1  # Default recommendation arm_id


@app.route('/', methods=['GET', 'POST'])
def index():
    no_results_message = ""
    show_results_label = False
    recommended_lm_titles = []
    search_recommendation = []
    
    arm_id = select_arm()
    # Retrieve the learning material titles for the selected arm
    cur.execute("SELECT lm_title FROM arms WHERE arm_id = %s", (arm_id,))
    rows = cur.fetchall()
    arm_recommendations = [row[0] for row in rows] if cur.rowcount > 0 else []
    recommended_lm_titles.extend(arm_recommendations)
    regretCalculation(arm_id)
    rewardCalculation(arm_id)

    if arm_id:
        updateArmSelection(arm_id)
        
    if request.method == 'POST':
        search_query = request.form.get('search_query', '')  # Use get() to avoid KeyError

        # Check if the search query is not empty
        if search_query.strip():
            arm_id = select_arm(search_query)
            
            # Retrieve the learning material titles for the selected arm
            cur.execute("SELECT lm_title FROM arms WHERE arm_id = %s", (arm_id,))
            rows = cur.fetchall()
            
            if rows:
                lm_title = rows[0][0]  # Extract lm_title from the first row

                # Check if the selected arm matches the search result
                cur.execute("SELECT arm_id FROM armsreward WHERE lower(lm_title) LIKE lower(%s) ORDER BY average_reward DESC LIMIT 1",
                            ('%{}%'.format(search_query),))
                search_id = cur.fetchone()[0] if cur.rowcount > 0 else None

                if arm_id == search_id:
                    cur.execute("SELECT lm_title FROM armsreward WHERE arm_id = %s", (arm_id,))
                    rows = cur.fetchall()
                    search_results = [row[0] for row in rows] if cur.rowcount > 0 else []
                    
                    if arm_id:
                        updateArmSelection(arm_id)
                    
                    if not search_results:
                        no_results_message = "No search results found. Try recommended learning material."
                    else:
                        show_results_label = True

                    search_recommendation.extend(search_results)
                else:
                    no_results_message = "No search results found. Try recommended learning material."

    return render_template('index.html', no_results_message=no_results_message,
                           show_results_label=show_results_label, recommended_lm_titles=recommended_lm_titles,
                           search_recommendation=search_recommendation)


@app.route('/click_resultquery/<lm_result>', methods=['GET'])
def click_resultquery(lm_result):
    # Retrieve the description of the clicked learning material
    cur.execute("SELECT description FROM arms WHERE lm_title = %s", (lm_result,))
    row = cur.fetchone()
    description = row[0] if row else "Description not found"
    
    cur.execute("SELECT arm_id FROM armsreward WHERE lm_title = %s", (lm_result,))
    row = cur.fetchone()
    id = row[0] if row else None
    
    # Update the armsreward table with the arm_id
    
    if (id):
        updateReward(id)
        observereward(id)
    
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
    # Use the PORT environment variable if available, otherwise default to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)