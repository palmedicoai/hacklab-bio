-- SQL script to create the 'user_personal_data' table in Supabase
-- This table stores personal and medical information for users
CREATE TABLE user_personal_data (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    gender TEXT,
    age INTEGER,
    chronological_age INTEGER,
    diabetes BOOLEAN,
    albumin FLOAT,
    creatinine FLOAT,
    glucose FLOAT,
    crp FLOAT, -- C-reactive protein
    lymphocyte_percent FLOAT,
    mcv FLOAT, -- Mean Cell Volume
    rdw FLOAT, -- Red Cell Distribution Width
    alkaline_phosphatase FLOAT,
    wbc_count FLOAT, -- White Blood Cell Count (10^3 cells/µL)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Optional: Add index for faster queries by email
CREATE INDEX idx_user_personal_data_email ON user_personal_data(email);
