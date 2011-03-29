
# alter table "net"
ALTER TABLE net ADD ip_version varchar(2) AFTER categoria;
ALTER TABLE net ADD rootnet smallint(1) DEFAULT '0' AFTER ip_version;
ALTER TABLE net CHANGE red red varchar(40);
ALTER TABLE net CHANGE BM BM varchar(3);

# update table net
#UPDATE net SET ip_version='v4' WHERE ip_version IS NULL;
UPDATE net SET ip_version='v4';


# alter table "host"
ALTER TABLE host ADD ip_version varchar(2) AFTER range_id;
ALTER TABLE host CHANGE ip ip varchar(40);
ALTER TABLE host ADD INDEX ip (ip);


# alter table "global_config"
ALTER TABLE global_config ADD ipv4_only varchar(3);

#update table "global_config"
UPDATE global_config set version='3.0';
UPDATE global_config set ipv4_only='yes';


# alter table "config"
ALTER TABLE config ADD smallest_bm6 varchar(3);

#update table "config"
UPDATE config set smallest_bm6='116';


# alter table "ranges"
ALTER TABLE ranges CHANGE start_ip start_ip varchar(40);
ALTER TABLE ranges CHANGE end_ip end_ip varchar(40);
