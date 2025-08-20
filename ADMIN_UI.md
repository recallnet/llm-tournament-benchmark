# AFBench Admin UI Specification

A comprehensive Streamlit dashboard for visualizing and exploring AFBench tournament results, model performance, and evaluation data. 

**CRITICAL**: The dashboard must ensure data integrity by working backwards from validated tournament results to prevent showing any invalidated or stale data.

## Profile-Aware Data Loading

### Understanding AFBench Profiles
AFBench uses Snakemake profiles to separate test and production environments:

- **Test Profile**: Uses `model_pools/test.csv` and `judge_pools/test.csv` (4 models, 3 judges)
- **Production Profile**: Uses `model_pools/production.csv` and `judge_pools/production.csv` (2 models, 1 judge)

### Profile Detection Strategy
The dashboard should automatically detect which profile was used for the current data:

```python
def detect_current_profile():
    """Detect which profile generated the current data."""
    with open('data/loaded_models.json') as f:
        models_data = json.load(f)
    
    pool_name = models_data['pool_info']['name']
    return pool_name  # Returns "test" or "production"

def get_profile_context():
    """Get context about the current profile."""
    profile = detect_current_profile()
    
    if profile == "test":
        return {
            'profile': 'test',
            'description': 'Test Environment',
            'models_expected': 4,
            'judges_expected': 3,
            'color': 'blue',
            'icon': '🧪'
        }
    elif profile == "production":
        return {
            'profile': 'production', 
            'description': 'Production Environment',
            'models_expected': 2,
            'judges_expected': 1,
            'color': 'green',
            'icon': '🚀'
        }
```

### Profile-Aware UI Elements
Display the current profile prominently in the dashboard:

```python
# In your main dashboard
profile_context = get_profile_context()

st.sidebar.markdown(f"""
## {profile_context['icon']} Environment
**{profile_context['description']}**  
Profile: `{profile_context['profile']}`
""")

# Color-code the entire dashboard based on profile
if profile_context['profile'] == 'test':
    st.markdown('<style>div.stApp > div:first-child { border-left: 5px solid blue; }</style>', unsafe_allow_html=True)
else:
    st.markdown('<style>div.stApp > div:first-child { border-left: 5px solid green; }</style>', unsafe_allow_html=True)
```

## Data Sources & Loading Strategy

### Primary Data Sources (Load Order)
The dashboard should load data in this specific order to ensure consistency:

1. **`data/skill_ratings.json`** - Start here as the authoritative source of completed tournaments
2. **`data/tournament_summaries.json`** - Match history and results for skills in ratings
3. **`data/loaded_models.json`** - Model pool information
4. **`data/loaded_judges.json`** - Judge pool information  
5. **`data/loaded_skills.json`** - Skills and evaluations metadata

### Secondary Data Sources (On-Demand)
6. **`data/conversations/{skill}/{eval_id}_{model_id}_{hash}.json`** - Individual conversation logs
7. **`data/intermediaries/{skill}/{eval_id}_intermediary_{step}_{model_id}_{hash}.json`** - Intermediary processing
8. **`data/tournaments/{skill}/{match_id}_{judge_id}_{hash}.json`** - Individual judge decisions

### Data Integrity Rules
- **Only show skills that exist in `skill_ratings.json`** - If a skill has no rating, don't display it
- **Only show matches from `tournament_summaries.json`** - This ensures completed tournaments only
- **Cross-reference all IDs** - Validate that model/judge/eval IDs exist across all data files
- **Cache Key Validation** - Use cache keys from ratings to validate data freshness

## Actual Data Structure (Based on Pipeline Analysis)

### Key Relationships in the Data Model
```
skill_ratings.json
├─ skill_ratings: {skill_id: rating_data}
├─ execution_info: {cache_key, timestamp, status}

tournament_summaries.json  
├─ tournaments: {skill_id: tournament_data}
│   ├─ skill_id: "document_summarization" 
│   ├─ total_matches: 6
│   ├─ model_rankings: [rank, points, win_rate]
│   ├─ match_history: [{match_id, model_a, model_b, judges, winner, timestamp}]
│   └─ evals: {eval_id: eval_specific_data}

loaded_skills.json
├─ skills: {skill_id: {eval_count, eval_ids, path}}
└─ evals: [{id, name, chain, judge, _metadata: {skill}}]
```

### File Naming Conventions
- Conversations: `{skill}/{eval_id}_{model_id}_{cache_hash}.json`
- Intermediaries: `{skill}/{eval_id}_intermediary_{step}_{model_id}_{cache_hash}.json`
- Judge Decisions: `{skill}/{match_id}_{judge_id}_{cache_hash}.json`
- Skill Ratings: `{skill_id}_{cache_key}.json`

### Current System State Example
Based on our testing, the system currently has:
```
Skills: 4 total
├─ document_summarization (1 eval: arxiv-2409-09684v2)
├─ respect_no_em_dash_requests (1 eval: black-swan-event)  
├─ code_generation (1 eval: algorithm_optimization)
└─ persuasiveness (1 eval: curiosity_killed_cat)

Models: 4 total
├─ inception/mercury
├─ openai/gpt-oss-120b  
├─ openai/gpt-oss-20b
└─ thedrummer/unslopnemo-12b

Current Winners by Skill:
├─ document_summarization: thedrummer/unslopnemo-12b (1525.28 rating)
├─ respect_no_em_dash_requests: openai/gpt-oss-20b (1580.75 rating)
├─ code_generation: openai/gpt-oss-20b (1584.51 rating)  
└─ persuasiveness: inception/mercury (1585.51 rating)
```

## Navigation Structure

### Main Navigation Pages
1. **Models** - Model pool overview and performance
2. **Judges** - Judge pool information and statistics
3. **Skills** - Skills overview and evaluation management
4. **Tournaments** - Tournament results and match analysis

---

## Page 1: Models

### Overview Table
Display all models from the latest run with key statistics:

| Column | Description |
|--------|-------------|
| Model ID | Full model identifier (e.g., `openai/gpt-4`) |
| Author | Model creator/organization |
| Context Window | Token limit |
| Endpoint | API provider |
| Skills Participated | Count of skills with tournaments |
| Total Matches | Across all skills |
| Overall Win Rate | Wins / Total Matches |
| Best Skill | Skill with highest rating |
| Worst Skill | Skill with lowest rating |

### Model Detail View
Click any model to see:
- **Performance by Skill**: Table showing rating, rank, W/L/T record per skill
- **Rating Evolution**: Charts showing OpenSkill rating progression over matches
- **Recent Matches**: Last 10 matches with opponents and outcomes
- **Conversation Quality**: Average response length, common patterns

---

## Page 2: Judges

### Overview Table
Display all judges from the latest run:

| Column | Description |
|--------|-------------|
| Judge ID | Full judge identifier |
| Author | Judge creator/organization |
| Context Window | Token limit |
| Total Decisions | Across all tournaments |
| Agreement Rate | How often agrees with majority |
| Swing Decisions | Close matches decided by this judge |
| Processing Speed | Average response time |

### Judge Detail View
Click any judge to see:
- **Decision Patterns**: Vote distribution (A/B/TIE percentages)
- **Consistency Analysis**: Agreement with other judges over time
- **Recent Decisions**: Last 10 judge decisions with reasoning
- **Performance by Skill**: Accuracy and consistency per evaluation domain

---

## Page 3: Skills

### Skills Overview
Grid layout showing all skills:

```
┌─ Document Summarization ─┐  ┌─ Code Generation ─┐
│ 2 Evaluations             │  │ 1 Evaluation       │
│ 48 Total Matches          │  │ 12 Total Matches   │
│ Last Run: 2 hours ago     │  │ Last Run: 3 hours  │
└───────────────────────────┘  └────────────────────┘

┌─ Persuasiveness ─────────┐  ┌─ Harm Avoidance ───┐
│ 3 Evaluations            │  │ 5 Evaluations       │
│ 72 Total Matches         │  │ 120 Total Matches   │
│ Last Run: 1 hour ago     │  │ Last Run: 4 hours   │
└──────────────────────────┘  └─────────────────────┘
```

### Skills Detail Page
Click any skill to navigate to dedicated skill page showing:

#### Evaluations Table
| Evaluation ID | Name | Type | Matches | Winner | Last Updated |
|---------------|------|------|---------|--------|--------------|
| arxiv-2409-09684v2 | ArXiv Paper Summary | Multi-step | 24 | inception/mercury | 2h ago |
| algorithm_optimization | Code Optimization | Single-step | 12 | openai/gpt-4 | 3h ago |

#### Evaluation Detail View
Click any evaluation to see:
- **Full JSON Payload**: Expandable code block with complete eval configuration
- **Evaluation Chain**: Visual representation of steps and dependencies
- **Sample Conversations**: Examples of model responses to this eval
- **Judge Instructions**: What judges look for in this evaluation

---

## Page 4: Tournaments

### Main Tournament Dashboard

#### Model Performance Matrix
Heatmap showing OpenSkill ratings by skill:

```
                           Doc Summ  Respect EM  Code Gen  Persuasive
thedrummer/unslopnemo-12b    1525.28    1416.09   1415.49    1414.48
openai/gpt-oss-120b          1507.02    1469.04   1531.10    1498.80
openai/gpt-oss-20b           1507.02    1580.75   1584.51    1501.20
inception/mercury            1460.68    1534.13   1468.90    1585.51
```

Colors: Green (1550+ rating) → Yellow (1500-1550) → Red (<1500 rating)

#### Tournament Navigation
Sidebar with expandable skill sections:
```
▼ Document Summarization
  └─ arxiv-2409-09684v2 (6 matches)
▼ Respect No Em Dash Requests  
  └─ black-swan-event (6 matches)
▼ Code Generation
  └─ algorithm_optimization (6 matches)
▼ Persuasiveness
  └─ curiosity_killed_cat (6 matches)
```

### Skill Tournament Page
Navigate to dedicated page for each skill showing:

#### Tournament Summary
- **Final Rankings**: Table with OpenSkill ratings, W/L/T records
- **Rating Progression**: Line chart showing how ratings evolved
- **Head-to-Head Matrix**: Win/loss records between all model pairs

#### Evaluation Breakdown
Tabs for each evaluation in the skill:
- **Match History**: Chronological list of all matches
- **Swiss Rounds**: Matches grouped by tournament rounds
- **Judge Statistics**: Voting patterns for this evaluation

### Match Detail View
Click any match to see comprehensive match analysis:

#### Match Header
```
Match ID: 6da18d129db51535
Evaluation: arxiv-2409-09684v2 (Document Summarization)
Timestamp: 2025-08-19T23:56:29.830246
Result: TIE (1A-1B-1T judge decision)
Cache Key: 3445216ed9db0646
```

#### Model Responses Section

**Model A: thedrummer/unslopnemo-12b**
- **Raw Conversation JSON**: 
  - Expandable code block with full conversation from `data/conversations/document_summarization/arxiv-2409-09684v2_thedrummer_unslopnemo-12b_{hash}.json`
  - Shows: model_id, eval_id, chain execution, step results, metadata
  - File path: `{skill}/{eval_id}_{model_id}_{cache_hash}.json`
- **Intermediary Thread** (if applicable):
  - Load from `data/intermediaries/{skill}/{eval_id}_intermediary_{step}_{model_id}_{hash}.json`
  - Shows secondary processing with intermediary models

**Model B: openai/gpt-oss-20b**  
- **Raw Conversation JSON**: Same format as Model A
- **Intermediary Thread** (if applicable): Same format as Model A

> **Implementation Note**: Use `load_conversation_log(skill, eval_id, model_id)` to fetch the actual JSON files with hash validation

#### Judge Decisions Section
Tabs for each judge showing full decision process:

**Judge: inception/mercury** (Voted: B)
- **Raw Judge JSON**: 
  - Expandable code block with complete judge decision from `data/tournaments/document_summarization/6da18d129db51535_inception_mercury_{hash}.json`
  - Shows: match metadata, judge conversation, vote parsing, reasoning
  - File path: `{skill}/{match_id}_{judge_id}_{cache_hash}.json`
- **Vote Extraction**: How the system parsed "B" from judge response
- **Judge Conversation**: Full prompt → judge response → vote extraction
- **Processing Metadata**: Timestamp, API response time, cache status

**Judge: thedrummer/unslopnemo-12b** (Voted: A)  
- **Raw Judge JSON**: Same format as above
- **Vote Extraction**: How the system parsed "A" from judge response

**Judge: openai/gpt-oss-20b** (Voted: TIE)
- **Raw Judge JSON**: Same format as above  
- **Vote Extraction**: How the system parsed "TIE" from judge response

> **Implementation Note**: Use `load_judge_decision(skill, match_id, judge_id)` to fetch individual judge decision files

#### Match Statistics
- **Agreement Level**: How much judges agreed (3-0, 2-1, etc.)
- **Decision Factors**: Key points mentioned by judges
- **Content Analysis**: Response length, complexity metrics
- **Historical Context**: How this match fits in tournament progression

### Advanced Features

#### Search and Filtering
- **Global Search**: Find matches by model, judge, evaluation, or content
- **Advanced Filters**: Date range, rating range, judge agreement level
- **Export Options**: Download match data, conversation logs, or analysis

#### Real-time Updates
- **Live Tournament Tracking**: Show matches in progress
- **Notification System**: Alert when tournaments complete
- **Data Refresh**: Auto-reload when new Snakemake data available

#### Analytics Dashboard
- **Performance Trends**: Model rating changes over time
- **Judge Reliability**: Consistency and agreement metrics
- **Evaluation Difficulty**: Which evals produce closest matches
- **System Health**: Cache hit rates, processing times, error rates

---

## Technical Implementation Notes

### Data Loading Implementation
```python
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_validated_tournament_data():
    """
    Load tournament data with data integrity validation.
    Starts from skill_ratings.json as authoritative source.
    """
    # Step 1: Load authoritative skill ratings
    with open('data/skill_ratings.json') as f:
        ratings_data = json.load(f)
    
    # Extract valid skills (only ones with completed ratings)
    valid_skills = set(ratings_data['skill_ratings'].keys())
    current_cache_key = ratings_data['execution_info']['cache_key']
    
    # Step 2: Load tournament summaries and filter to valid skills only
    with open('data/tournament_summaries.json') as f:
        tournaments_data = json.load(f)
    
    validated_tournaments = {
        skill: data for skill, data in tournaments_data['tournaments'].items()
        if skill in valid_skills
    }
    
    # Step 3: Load metadata files
    with open('data/loaded_models.json') as f:
        models_data = json.load(f)
    with open('data/loaded_judges.json') as f:
        judges_data = json.load(f) 
    with open('data/loaded_skills.json') as f:
        skills_data = json.load(f)
    
    # Step 4: Profile validation and context
    current_profile = detect_current_profile()
    profile_context = get_profile_context()
    
    # Validate expected counts for the profile
    actual_models = len(models_data['models'])
    actual_judges = len(judges_data['judges'])
    
    warnings = []
    if actual_models != profile_context['models_expected']:
        warnings.append(f"Expected {profile_context['models_expected']} models for {current_profile} profile, found {actual_models}")
    if actual_judges != profile_context['judges_expected']:
        warnings.append(f"Expected {profile_context['judges_expected']} judges for {current_profile} profile, found {actual_judges}")
    
    # Step 5: Cross-validate all IDs exist
    model_ids = {m['id'] for m in models_data['models']}
    judge_ids = {j['id'] for j in judges_data['judges']} 
    eval_ids = {e['id'] for e in skills_data['evals']}
    
    return {
        'valid_skills': valid_skills,
        'cache_key': current_cache_key,
        'profile': current_profile,
        'profile_context': profile_context,
        'profile_warnings': warnings,
        'models': models_data,
        'judges': judges_data,
        'skills': skills_data,
        'tournaments': validated_tournaments,
        'ratings': ratings_data['skill_ratings'],
        'model_ids': model_ids,
        'judge_ids': judge_ids,
        'eval_ids': eval_ids
    }

@st.cache_data(ttl=60)  # Shorter cache for drill-down data
def load_conversation_log(skill: str, eval_id: str, model_id: str):
    """Load individual conversation log with hash validation."""
    pattern = f"data/conversations/{skill}/{eval_id}_{model_id}_*.json"
    matches = glob.glob(pattern)
    if not matches:
        return None
    
    # Use most recent if multiple matches
    latest_file = max(matches, key=os.path.getmtime)
    with open(latest_file) as f:
        return json.load(f)

@st.cache_data(ttl=60)
def load_judge_decision(skill: str, match_id: str, judge_id: str):
    """Load individual judge decision with hash validation."""
    pattern = f"data/tournaments/{skill}/{match_id}_{judge_id}_*.json"
    matches = glob.glob(pattern)
    if not matches:
        return None
        
    latest_file = max(matches, key=os.path.getmtime)
    with open(latest_file) as f:
        return json.load(f)
```

### Page State Management
- Use `st.session_state` for navigation and drill-down state
- Preserve filters and selections across page refreshes
- Deep linking support for sharing specific views

### Performance Optimization
- Lazy loading of large conversation logs
- Pagination for long match lists
- Efficient caching of expensive computations
- Progressive data loading for better UX

### Security Considerations
- Read-only access to all data files
- No ability to modify tournaments or evaluations
- Safe rendering of user-generated content
- Input validation for search and filters

### Critical: Cache Validation & Data Freshness
```python
def validate_data_freshness():
    """
    Ensure all displayed data is from the same cache generation.
    Show warning if data files have mismatched cache keys.
    """
    ratings_cache_key = load_skill_ratings()['execution_info']['cache_key']
    
    # Check all skill rating files use same cache key
    skill_rating_files = glob.glob('data/skill_ratings/*.json')
    for file in skill_rating_files:
        if ratings_cache_key not in file:
            st.warning(f"⚠️ Stale data detected: {file}")
    
    # Show data freshness indicator
    st.sidebar.info(f"🔑 Cache Key: {ratings_cache_key}")
    st.sidebar.info(f"🕐 Last Updated: {timestamp}")
```

### Error Handling for Missing Files
- **Graceful Degradation**: If conversation/judge files are missing, show metadata only
- **File Not Found**: Display "Data not available" instead of crashing
- **Hash Mismatch**: Warn user about potentially stale data
- **Partial Data**: Clearly indicate when drill-down data is incomplete

## Profile Management & Data Refresh

### Profile Switching Instructions
Tell your users how to switch between profiles and refresh data:

```python
# Add this to your sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Data Management")

# Show current profile
current_profile = detect_current_profile()
st.sidebar.info(f"Current Profile: **{current_profile}**")

# Instructions for switching
st.sidebar.markdown("""
**To switch environments:**
1. Run in terminal: `snakemake --profile profiles/test` OR `snakemake --profile profiles/production`
2. Click "Refresh Data" button below
3. Dashboard will automatically detect the new profile

**To refresh current data:**
- Click "Refresh Data" to reload from disk
- Data auto-refreshes every 5 minutes
""")

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()  # Clear all cached data
    st.experimental_rerun()  # Refresh the app
```

### Profile-Specific Navigation Hints
Adapt your navigation based on the current profile:

```python
def get_navigation_context(profile):
    """Get profile-specific navigation hints."""
    if profile == "test":
        return {
            'hint': "🧪 Test Environment - Use for development and testing",
            'models_note': "4 test models available",
            'judges_note': "3 judge models available",
            'performance_note': "Lower-cost models, faster execution"
        }
    else:
        return {
            'hint': "🚀 Production Environment - Live model evaluations",
            'models_note': "2 production models available", 
            'judges_note': "1 production judge available",
            'performance_note': "High-quality models, slower execution"
        }

# Use in your main pages
nav_context = get_navigation_context(current_profile)
st.info(nav_context['hint'])
```

### Data Consistency Across Profiles
**Important**: Each profile maintains separate cache files and data integrity:

- **Test data** and **production data** never mix
- **Cache keys** are different between profiles (different models = different cache keys)
- **Tournaments** run independently for each profile
- **Skills and evaluations** remain the same across profiles (only models/judges change)

This dashboard provides comprehensive visibility into the AFBench system while maintaining the data-driven approach and cache integrity established by the Snakemake pipeline. The key principle is **never show invalidated data** - always start from `skill_ratings.json` as the source of truth and work backwards to ensure consistency.