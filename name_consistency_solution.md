# Employee Name Consistency Solution

## Problem
Employee names appear differently across fields:
- Employee: "Esmaya Purcell"
- Commissions: "Esmaya: -130" or "Esmaya Purcell: 50.00"
- Variations: "Esmaya", "Esmaya P.", "E. Purcell", etc.

## Best Solutions (Ranked)

### Option 1: Employee Lookup Table (RECOMMENDED)
Create a master employee table in Airtable and use linked records.

**Steps:**
1. Create new table: "Employees"
2. Add fields:
   - Name (Primary)
   - Full Name (canonical name)
   - Aliases (text field for variations)
3. Link Employee field in Sales table to Employees table
4. Use formula to extract and match names

**Benefits:**
- Single source of truth
- Easy to maintain
- Automatic consistency
- Can add employee details (email, department, etc.)

### Option 2: Name Normalization in Code Node
Add name matching logic to your n8n workflow.

**Approach:**
- Create employee name mapping
- Normalize names during data processing
- Match variations to canonical names

### Option 3: Fuzzy Matching
Use similarity algorithms to match similar names.

**Approach:**
- Compare name strings
- Match based on similarity score
- Handle typos and variations

### Option 4: Post-Processing Script
Clean names after data is in Airtable.

**Approach:**
- Run Python script periodically
- Update records with normalized names
- Maintain mapping table

---

## Implementation: Code Node Solution

### Updated Code with Name Normalization

Add this to your n8n Code node:

```javascript
// Employee name mapping - add all known variations
const employeeNameMap = {
  // Format: 'variation': 'canonical_name'
  'esmaya': 'Esmaya Purcell',
  'esmaya purcell': 'Esmaya Purcell',
  'e. purcell': 'Esmaya Purcell',
  'esmaya p.': 'Esmaya Purcell',
  
  'tharuka': 'Tharuka Selliah',
  'tharuka selliah': 'Tharuka Selliah',
  't. selliah': 'Tharuka Selliah',
  'tharuka s.': 'Tharuka Selliah',
  
  'christabel': 'Christabel Fashola',
  'christabel fashola': 'Christabel Fashola',
  'c. fashola': 'Christabel Fashola',
  
  'bisma': 'Bisma Bukhari',
  'bisma bukhari': 'Bisma Bukhari',
  'b. bukhari': 'Bisma Bukhari',
  
  // Add more employees as needed
};

// Function to normalize employee name
function normalizeEmployeeName(name) {
  if (!name || name === 'NaN' || name === '') {
    return '';
  }
  
  // Convert to lowercase for matching
  const nameLower = name.trim().toLowerCase();
  
  // Direct match
  if (employeeNameMap[nameLower]) {
    return employeeNameMap[nameLower];
  }
  
  // Check if name contains any mapped variation
  for (const [variation, canonical] of Object.entries(employeeNameMap)) {
    if (nameLower.includes(variation) || variation.includes(nameLower)) {
      return canonical;
    }
  }
  
  // If no match found, return original (capitalize first letter of each word)
  return name.split(' ').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
  ).join(' ');
}

// Function to extract employee name from Commissions
function extractEmployeeFromCommissions(commissionsString) {
  if (!commissionsString || commissionsString === 'NaN' || commissionsString === '') {
    return '';
  }
  
  // Commissions format: "Esmaya: -130" or "Esmaya Purcell: -130"
  const colonIndex = commissionsString.indexOf(':');
  if (colonIndex > 0) {
    const name = commissionsString.substring(0, colonIndex).trim();
    return normalizeEmployeeName(name);
  }
  
  return normalizeEmployeeName(commissionsString);
}
```

### Updated Main Processing Code

In your main loop, replace the employee handling:

```javascript
// Normalize employee names
let employee = normalizeEmployeeName(json['Employee'] || '');
let commissions = json['Commissions'] || '';

// If Gross Sales is negative (refund), extract from Commissions
if (grossSales < 0) {
  refunds = grossSales;
  finalGrossSales = 0;
  
  // Extract and normalize employee from Commissions
  const employeeFromCommissions = extractEmployeeFromCommissions(commissions);
  if (employeeFromCommissions) {
    employee = employeeFromCommissions;
    commissions = employeeFromCommissions; // Store normalized name
  }
} else {
  // For regular sales, normalize the commissions field too
  const employeeFromCommissions = extractEmployeeFromCommissions(commissions);
  if (employeeFromCommissions && employeeFromCommissions === employee) {
    commissions = employeeFromCommissions; // Use normalized name
  }
}
```

---

## Implementation: Airtable Solution

### Step 1: Create Employees Table

1. Create new table: "Employees"
2. Fields:
   - **Name** (Single line text) - Primary field
   - **Full Name** (Single line text) - Canonical name
   - **Aliases** (Long text) - Variations separated by commas
   - **Email** (Email) - Optional
   - **Active** (Checkbox) - Optional

### Step 2: Populate Employees Table

| Name | Full Name | Aliases |
|------|-----------|--------|
| Esmaya | Esmaya Purcell | Esmaya, E. Purcell, Esmaya P. |
| Tharuka | Tharuka Selliah | Tharuka, T. Selliah, Tharuka S. |
| Christabel | Christabel Fashola | Christabel, C. Fashola |
| Bisma | Bisma Bukhari | Bisma, B. Bukhari |

### Step 3: Create Formula Field in Sales Table

**Employee Lookup** (Formula):
```
IF(
  FIND(LOWER(LEFT({Employee}, FIND(" ", {Employee} & " ") - 1)), 
       LOWER({Employees::Aliases})) > 0,
  {Employees::Full Name},
  {Employee}
)
```

### Step 4: Use Linked Records

1. Change Employee field type to "Link to another record"
2. Link to Employees table
3. Use automation to auto-link based on name matching

---

## Implementation: Python Post-Processing

### Name Cleaning Script

```python
import pandas as pd
from airtable import Airtable
from difflib import SequenceMatcher

# Employee name mapping
EMPLOYEE_MAP = {
    'esmaya': 'Esmaya Purcell',
    'esmaya purcell': 'Esmaya Purcell',
    'tharuka': 'Tharuka Selliah',
    'tharuka selliah': 'Tharuka Selliah',
    # Add more mappings
}

def normalize_name(name):
    """Normalize employee name to canonical form"""
    if not name or pd.isna(name):
        return ''
    
    name_lower = str(name).strip().lower()
    
    # Direct match
    if name_lower in EMPLOYEE_MAP:
        return EMPLOYEE_MAP[name_lower]
    
    # Partial match
    for key, value in EMPLOYEE_MAP.items():
        if key in name_lower or name_lower in key:
            return value
    
    # Return capitalized original
    return ' '.join(word.capitalize() for word in name.split())

def fuzzy_match(name1, name2):
    """Calculate similarity between two names"""
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

# Connect to Airtable
airtable = Airtable(BASE_ID, TABLE_NAME, API_KEY)
records = airtable.get_all()

# Normalize names
for record in records:
    fields = record['fields']
    
    # Normalize Employee
    if 'Employee' in fields:
        normalized = normalize_name(fields['Employee'])
        if normalized != fields['Employee']:
            airtable.update(record['id'], {'Employee': normalized})
    
    # Normalize Commissions (extract name part)
    if 'Commissions' in fields:
        comm = fields['Commissions']
        if ':' in comm:
            name_part = comm.split(':')[0].strip()
            normalized = normalize_name(name_part)
            # Update if different
            if normalized != name_part:
                new_comm = comm.replace(name_part, normalized)
                airtable.update(record['id'], {'Commissions': new_comm})

print("Name normalization complete!")
```

---

## Best Practice: Hybrid Approach

### Recommended Workflow:

1. **In Code Node (n8n)**:
   - Basic normalization
   - Extract names from Commissions
   - Match to known variations

2. **In Airtable**:
   - Create Employees lookup table
   - Use formulas for consistency
   - Manual review for edge cases

3. **Periodic Cleanup**:
   - Run Python script monthly
   - Update employee mapping
   - Fix any inconsistencies

---

## Quick Fix: Update Your Current Code

Here's the minimal change to add to your existing code node:

Add at the top (after other functions):

```javascript
// Employee name normalization map
const employeeMap = {
  'esmaya': 'Esmaya Purcell',
  'tharuka': 'Tharuka Selliah',
  'christabel': 'Christabel Fashola',
  'bisma': 'Bisma Bukhari',
  // Add all your employees here
};

function normalizeName(name) {
  if (!name) return '';
  const key = name.trim().toLowerCase();
  return employeeMap[key] || name;
}
```

Then in your main loop, update:

```javascript
let employee = normalizeName(json['Employee'] || '');
let commissions = json['Commissions'] || '';

if (grossSales < 0) {
  // ... refund logic ...
  const empFromComm = extractEmployeeFromCommissions(commissions);
  if (empFromComm) {
    employee = normalizeName(empFromComm);
    commissions = employee; // Use normalized name
  }
}
```

---

## Maintenance Tips

1. **Keep Employee Map Updated**: Add new employees as they appear
2. **Review Regularly**: Check for new name variations
3. **Use Airtable Views**: Filter by employee to spot inconsistencies
4. **Automate**: Set up n8n workflow to flag name mismatches

---

## Which Solution to Use?

- **Quick Fix**: Add normalization to Code Node (5 minutes)
- **Long-term**: Create Employees table in Airtable (30 minutes)
- **Advanced**: Python post-processing script (for complex cases)

I recommend starting with the Code Node solution, then moving to Airtable Employees table for better long-term management.
