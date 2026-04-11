const fs = require('fs');
const { Client } = require('pg');

const run = async () => {
    // using the direct database connection instead of the connection pooler
    const connectionString = "postgresql://postgres:sb_secret_jfZ7uS_Srt2UHGzKjbOc_w_2TW-BCkZ@db.mahqnqoeehbsctmtjked.supabase.co:5432/postgres";
    
    const client = new Client({
        connectionString,
        ssl: { rejectUnauthorized: false }
    });

    try {
        await client.connect();
        console.log("Connected to Supabase.");

        const sql = fs.readFileSync('schema.sql', 'utf8');
        console.log("Executing schema.sql...");
        
        await client.query(sql);
        console.log("Schema established successfully!");
        
    } catch (err) {
        console.error("Error executing schema:");
        console.error(err.message);
    } finally {
        await client.end();
    }
};

run();
