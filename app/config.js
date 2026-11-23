// Connexion du site à la base de test Supabase (décision 0006).
// L'adresse et la clé « publishable » / « anon » sont faites pour être visibles dans une page web :
// elles ne donnent accès qu'à ce que les règles de la base autorisent (migrations/003_droits.sql).
// NE JAMAIS mettre ici la clé « secret » / « service_role » ni le mot de passe de la base.
window.ZENITUDE_CONFIG = {
  supabaseUrl: "https://jukuciixzrixmaqunpbu.supabase.co",
  supabaseCle: "COLLER_ICI_LA_CLE_PUBLIQUE"
};
