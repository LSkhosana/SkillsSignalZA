-- Package L.1: lock the immutable-history trigger function search_path.
-- The function only raises a controlled exception and does not need public.

ALTER FUNCTION public.skillsignalza_reject_immutable_update()
    SET search_path = pg_catalog;
