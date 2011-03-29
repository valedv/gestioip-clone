#!/usr/bin/perl -w -T

# Script for importing networks from the routing tables via SNMP
# into the database of GestioIP.
# you have to adapt this script. See documentation for more information

# Copyright (C) 2011 Marc Uebel

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# VERSION 2.2.8.0

use lib '/var/www/gestioip/modules';
use GestioIP;
use strict;
use SNMP;
use Net::IP;
use DBI;
use Mail::Mailer;
use FindBin qw($Bin);
use Getopt::Long;
Getopt::Long::Configure ("no_ignore_case");
use Fcntl qw(:flock);


my $gip = GestioIP -> new();

my $VERSION="3.0.0";

my $smallest_bitmask="16";

my $set_sync_flag="1";

# Set route_proto_other to "1" if you want that routes with ipRouteProto=other(1)
# be added to GestioIP's database. Default="0" 
my $route_proto_other="0";

my ( $disable_audit, $quiet, $help, $version_arg, $configuration_arg,$community,$snmp_version,$client_id,$lang,$ini_devices,$gip_config_file,$user,$add_comment, $max_sync_procs);
my $auth_proto="";
my $auth_pass="";
my $priv_proto="";
my $priv_pass="";
my $sec_level="";


GetOptions(
        "community=s"=>\$community,
        "id_client=s"=>\$client_id,
        "snmp_version=s"=>\$snmp_version,
        "lang=s"=>\$lang,
        "user=s"=>\$user,
        "devices=s"=>\$ini_devices,
        "procs=s"=>\$max_sync_procs,
        "gestioip_config=s"=>\$gip_config_file,
        "quiet!"=>\$quiet,
	"add_comment!"=>\$add_comment,
	"Version!"=>\$version_arg,
	"n=s"=>\$auth_proto,
	"o=s"=>\$auth_pass,
	"t=s"=>\$priv_proto,
	"q=s"=>\$priv_pass,
	"r=s"=>\$sec_level,
#        "disable_audit!"=>\$disable_audit,
        "help!"=>\$help
) or print_help();

if ( ! $client_id ) {
        print STDERR "Parameter \"client_id\" missing\n";
        exit 1;
}
if ( ! $gip_config_file ) {
        print STDERR "Parameter \"gestioip_config\" missing";
        exit 1;
}

$client_id =~ /^(\d{1,5})$/;
$client_id = $1;

my $dir = $Bin;
$dir =~ /^(.*\/bin\/web)$/;
$dir = $1;
$dir =~ /^(.*)\/bin/;
my $base_dir=$1;

my $lockfile = $base_dir . "/var/run/" . $client_id . "_web_get_networks_snmp.lock";

no strict 'refs';
open($lockfile, '<', $0) or die("Unable to create lock file: $!\n");
use strict;

unless (flock($lockfile, LOCK_EX|LOCK_NB)) {
        print LOG "$0 is already running. Exiting.\n";
        exit(1);
}

my $pidfile = $base_dir . "/var/run/" . $client_id . "_web_get_networks_snmp.pid";
$pidfile =~ /^(.*_web_get_networks_snmp.pid)$/;
$pidfile = $1;
open(PID,">$pidfile") or die("Unable to create pid file $pidfile: $! (2)\n");
print PID $$;
close PID;

$SIG{'TERM'} = $SIG{'INT'} = \&do_term;


$lang = "en" if ! $lang;

$add_comment="1" if $add_comment;
$add_comment="0" if ! $add_comment;

my ($s, $mm, $h, $d, $m, $y) = (localtime) [0,1,2,3,4,5];
$m++;
$y+=1900;
if ( $d =~ /^\d$/ ) { $d = "0$d"; }
if ( $s =~ /^\d$/ ) { $s = "0$s"; }
if ( $m =~ /^\d$/ ) { $m = "0$m"; }
if ( $mm =~ /^\d$/ ) { $mm = "0$mm"; }
my $mydatetime = "$y-$m-$d $h:$mm:$s";


$gip_config_file =~ /^(.*)\/priv/;
my $gestioip_root=$1;
my $ini_stat=$gestioip_root . "/status/ini_stat.html";
my $log=$gestioip_root . "/status/" . $client_id . "_initialize_gestioip.log";
$log =~ /^(.*_initialize_gestioip.log)$/;
$log = $1;

if ( ! -d "${gestioip_root}/status" ) {
        print STDERR "Log directory does not exists: ${gestioip_root}/status\n\exiting\n";
	exit 1;
}
open(LOG,">>$log") or die "$log: $!\n";
*STDERR = *LOG;

if ( ! $community ) {
        print LOG "Parameter \"community\" missing\n";
	close LOG;
        exit 1;
}
if ( ! $snmp_version ) {
        print LOG "Parameter \"snmp_version\" missing\n";
	close LOG;
        exit 1;
}
if ( ! $ini_devices ) {
        print LOG "Parameter \"devices\" missing";
	close LOG;
        exit 1;
}
if ( ! -r $gip_config_file ) {
        print LOG "config_file $gip_config_file not readable\n\nexiting\n";
	close LOG;
        exit 1;
}



$dir =~ /^(.*)\/bin/;
my $vars_dir=$1;
my $vars_file=$vars_dir . "/etc/vars/vars_update_gestioip_" . "$lang";
if ( ! -r $vars_file ) {
        print LOG "vars_file not found: $vars_file\n\exiting\n";
	close LOG;
        exit 1;
}


my %lang_vars;

open(LANGVARS,"<$vars_file") or die "Can no open $vars_file: $!\n";
while (<LANGVARS>) {
        chomp;
        s/#.*//;
        s/^\s+//;
        s/\s+$//;
        next unless length;
        my ($var, $value) = split(/\s*=\s*/, $_, 2);
        $lang_vars{$var} = $value;
}
close LANGVARS;

my $community_type="Community";

my $auth_is_key="";
my $priv_is_key="";

if ( $snmp_version == "3" ) {
	$community_type = "SecName";
	if ( ! $community ) {
		print LOG "No Username\n";
		close LOG;
		exit(1);
	}
#       {introduce_community_string_message}") if ! $community;
	if ( $auth_proto && ! $auth_pass ) {
		print LOG "No auth password\n";
		close LOG;
		exit(1);
	}
#       $gip->print_error("$client_id","$$lang_vars{introduce_auth_pass_message}") if $auth_proto && ! $auth_pass;
	if ( $auth_pass && ! $auth_proto ) {
		print LOG "No auth protocol\n";
		close LOG;
		exit(1);
	}
#       $gip->print_error("$client_id","$$lang_vars{introduce_auth_proto_message}") if $auth_pass && ! $auth_proto;
	if ( $priv_proto && ! $priv_pass ) {
		print LOG "No privacy password\n";
		close LOG;
		exit(1);
	}
#       $gip->print_error("$client_id","$$lang_vars{introduce_priv_pass_message}") if $priv_proto && ! $priv_pass;
	if ( $priv_pass && ! $priv_proto ) {
		print LOG "No privacy protocol\n";
		close LOG;
		exit(1);
	}
#       $gip->print_error("$client_id","$$lang_vars{introduce_priv_proto_message}") if $priv_pass && ! $priv_proto;
	if ( $priv_proto && ( ! $auth_proto || ! $auth_pass ) ) {
		print LOG "No \"auth algorithm\" and \"auth password/auth key\"\n";
		close LOG;
		exit(1);
	}
}

my $gip_version=get_version() || "";

if ( $VERSION !~ /$gip_version/ ) {
        print LOG "\nScript and GestioIP version are not compatible\n\nGestioIP version: $gip_version - script version: $VERSION\n\n";
        exit 1;
}


my @config = get_config("$client_id");
my $ignorar = $config[0]->[2] || "";
my $ignore_generic_auto = $config[0]->[3] || "yes";
my $generic_dyn_host_name = $config[0]->[4] || "";
my $dyn_ranges_only = $config[0]->[5] || "n";
my $ping_timeout = $config[0]->[6] || "2";

if ( ! $config[0] ) {
	print LOG "Can't fetch config\n\nexiting\n";
}

my $audit_type="44";
my $audit_class="2";
my $update_type_audit="3";
my $event="---";
insert_audit_auto("$audit_class","$audit_type","$event","$update_type_audit","$client_id","$user");



my $red_num = get_last_red_num() || "1";

my @all_db_networks = get_all_networks("$client_id");

my $node;


$ini_devices =~ s/^\s*//;
$ini_devices =~ s/[\s\n\t]*$//;
my @nodes = split(",",$ini_devices);
my $i="0";

if ( ! $nodes[0] ) {
	print LOG "\nNo nodes to query found\n\n";
	exit 1;
}

my $new_net_count="0";
my @found_networks = ();

my $ip_version="v4";

foreach ( @nodes ) {
	$new_net_count="0";
	$node = $_;
	print LOG "\n+++ Importing networks from $node +++\n\n";

#	my $session = new SNMP::Session(DestHost => $node, Community => $community,
#				     Version => 1,
#				     UseSprintValue => 1);
#	unless (defined $session) {
#		print LOG "Can't connect to $node (1)";
#		mod_ini_stat("$new_net_count");
#		next;
#	}

	my $gip_vars_file=${gestioip_root} . "/vars/vars_" . $lang;
	if ( ! -r $gip_vars_file ) {
		print LOG "Can not open gip_vars_file ($gip_vars_file): $!\n";
		close LOG;
		exit(1);
	}
	my $session=$gip->create_snmp_session("$client_id","$node","$community","$community_type","$snmp_version","$auth_pass","$auth_proto","$auth_is_key","$priv_proto","$priv_pass","$priv_is_key","$sec_level","$gip_vars_file");

	
	### ipCidrRouteDest

	my ($ipRouteProto,$route_dest_cidr,$route_dest_cidr_mask);

	my $vars = new SNMP::VarList(['ipCidrRouteDest'],
			    	['ipCidrRouteMask'],
				['ipCidrRouteProto']);

	# get first row
	($route_dest_cidr) = $session->getnext($vars);
	if ($session->{ErrorStr}) {
		print LOG "Can't connect to $node (2)\n";
		mod_ini_stat("$new_net_count");
		next;
	}

	# and all subsequent rows
	my @route_dests_cidr;
	my $l = "0";
	while (!$session->{ErrorStr} and 
	       $$vars[0]->tag eq "ipCidrRouteDest"){
		($route_dest_cidr,$route_dest_cidr_mask,$ipRouteProto) = $session->getnext($vars);
		my $comment;
		if ( $ipRouteProto =~ /local/ ) {
			$comment = "Local route from $node" if $add_comment == "1";
		} elsif ( $ipRouteProto =~ /netmgmt/ ) {
			$comment = "Static route from $node" if $add_comment == "1";
		} elsif ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) {
			$comment = "route from $node (proto: other)" if $add_comment == "1";
		}
		if ( $ipRouteProto =~ /local/ || $ipRouteProto =~ /netmgmt/ || ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) ) {
			if ( $route_dest_cidr_mask =~ /\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/ ) {
				$route_dest_cidr_mask =~ /(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/;
				$route_dest_cidr_mask = $4 . "." . $3 . "." . $2 . "." . $1;
			}
			if ( $add_comment == "1" ) {
				$route_dests_cidr[$l] = "$route_dest_cidr/$route_dest_cidr_mask/$comment"; 
			} else {
				$route_dests_cidr[$l] = "$route_dest_cidr/$route_dest_cidr_mask"; 
			}
		}
		$l++;
	};


	### ipRouteDest

	my ($route_dest,$route_mask,$route_proto);

	$vars = new SNMP::VarList(['ipRouteDest'],
			    	['ipRouteMask'],
				['ipRouteProto']);

	# get first row
	($route_dest) = $session->getnext($vars);
	if ($session->{ErrorStr}) {
		print LOG "Can't connect to $node\n";
		mod_ini_stat("$new_net_count") unless
		next;
	}

	# and all subsequent rows
	while (!$session->{ErrorStr} and 
	       $$vars[0]->tag eq "ipRouteDest"){
		($route_dest,$route_mask,$route_proto) = $session->getnext($vars);
		my $comment;
		if ( $route_proto =~ /local/ ) {
			$comment = "Local route from $node" if $add_comment == "1";
		} elsif ( $route_proto =~ /netmgmt/ ) {
			$comment = "Static route from $node" if $add_comment == "1";
		} elsif ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) {
			$comment = "route from $node (proto: other)" if $add_comment == "1";
		}
		if ( $route_proto =~ /local/ || $route_proto =~ /netmgmt/ || ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) ) {
			if ( $add_comment == "1" ) {
				$route_dests_cidr[$l] = "$route_dest/$route_mask/$comment"; 
			} else {
				$route_dests_cidr[$l] = "$route_dest/$route_mask"; 
			}
		}
		$l++;
	};

	# delete duplicated entries
	my %seen = ();
	my $item;
	my @uniq;
	foreach $item(@route_dests_cidr) {
		next if ! $item;
		push(@uniq, $item) unless $seen{$item}++;
	}
	@route_dests_cidr = @uniq;


	my ($network_cidr_mask, $network_no_cidr, $BM);

	foreach $network_cidr_mask(@route_dests_cidr) {
		next if ! $network_cidr_mask;
		next if $network_cidr_mask =~ /0.0.0.0/ || $network_cidr_mask =~ /169.254.0.0/;
		my ($network,$mask,$comment);
		if ( $add_comment == "1" ) {
			($network,$mask,$comment) = split("/",$network_cidr_mask);
		} else {
			($network,$mask) = split("/",$network_cidr_mask);
		}
		# Convert netmasks to bitmasks
		$BM=convert_mask("$network","$mask");
		next if ! $BM; 
		
		# check if bitmask is to small
		if ( $BM < $smallest_bitmask ) {
			print LOG "$network/$BM: Bitmask to small - IGNORED\n";
			next;
		} 

		# Check for overlapping networks
		my $overlap = check_overlap("$network","$BM",\@all_db_networks);

		next if $overlap eq "1";

		# add the network to @all_db_networks to include it in the overlap check
		# for the next network
		my $l = @all_db_networks;
		$all_db_networks[$l]->[0] = $network;
		$all_db_networks[$l]->[1] = $BM;

		# insert networks into the database
		print LOG "$network/$BM: ADDED\n";
		$red_num++;
	
		if ( $add_comment == "1" ) {
			insert_networks($network,$BM,$red_num,$comment,$client_id,$set_sync_flag,"$ip_version");
		} else {
			insert_networks($network,$BM,$red_num,"",$client_id,$set_sync_flag,"$ip_version");
		}
		push (@found_networks,$red_num);
		my $audit_type="17";
		my $audit_class="2";
		my $update_type_audit="3";
		my $descr="---";
		$comment="---" if ! $comment;
		my $vigilada = "n";
		my $site_audit = "---";
		my $cat_audit = "---";

		my $event="$network/$BM,$descr,$site_audit,$cat_audit,$comment,$vigilada";
		$event=$event . " (community: public)" if $community eq "public";
		insert_audit_auto("$audit_class","$audit_type","$event","$update_type_audit","$client_id","$user");
		$new_net_count++;

	}
	#change ini_stat.html
	mod_ini_stat("$new_net_count");
}

open (FN,">${base_dir}/var/run/${client_id}_found_networks.tmp") or die "Can't open ${base_dir}/var/run/${client_id}_found_networks.tmp\n";
foreach my $line ( @found_networks ) {
	print FN $line . "\n";
}
close FN;


close LOG;

unlink("$pidfile");

exit 0;

#################
## subroutines ##
#################


sub insert_networks {
        my ($network,$BM,$red_num,$comment,$client_id,$set_sync_flag) = @_;
	if ( $set_sync_flag eq "1" ) {
		$set_sync_flag = "y";
	} else {
		$set_sync_flag = "n";
	}
		 
	$comment = '' if ( ! $comment );
	my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $sth = $dbh->prepare("INSERT INTO net (red,bm,descr,red_num,loc,vigilada,comentario,categoria,ip_version,client_id) VALUES ( \"$network\", \"$BM\", \"\",\"$red_num\",\"-1\",\"$set_sync_flag\",\"$comment\",\"-1\",\"$ip_version\",\"$client_id\")"
                                ) or die "Fehler bei insert db: $DBI::errstr\n";
        $sth->execute() or die "Fehler bei execute db: $DBI::errstr\n";
        $sth->finish();
        $dbh->disconnect;
}


sub get_last_red_num {
        my $red_num;
	my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $sth = $dbh->prepare("SELECT red_num FROM net ORDER BY (red_num+0) DESC LIMIT 1
                        ") or die "$dbh->errstr";
        $sth->execute() or die "Can not execute statement: $sth->errstr";
        $red_num = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $red_num;
}


sub get_all_networks {
	my ($client_id) = @_;
        my @overlap_redes;
        my $ip_ref;
	my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $sth = $dbh->prepare("SELECT red, BM FROM net WHERE client_id = \"$client_id\" ORDER BY INET_ATON(red)") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @overlap_redes, [ @$ip_ref ];
        }
        $dbh->disconnect;
        return @overlap_redes;
}

sub check_overlap {
        my ( $red, $BM, $overlap_redes ) = @_;
        my $k="0";
        my $overlap = "0";
        my $ip = new Net::IP ("$red/$BM") or print LOG "$red/$BM network/bitmask INVALID - IGNORED\n";
        if ( $ip ) {
                foreach (@{$overlap_redes}) {
                        my $red2 = "@{$overlap_redes}[$k]->[0]";
                        my $BM2 = "@{$overlap_redes}[$k]->[1]";
                        my $ip2 = new Net::IP ("$red2/$BM2") or print LOG "$red2/$BM2 INVALID network/bitmask - IGNORED\n";
                        if ( ! $ip2 ) { next; }

                        if ($ip->overlaps($ip2)==$IP_A_IN_B_OVERLAP) {
                                print LOG "$red/$BM overlaps with $red2/$BM2 -  IGNORED\n";
                                $overlap = "1";
                                last;
                        }
                        if ($ip->overlaps($ip2)==$IP_B_IN_A_OVERLAP) {
                                print LOG "$red/$BM overlaps with $red2/$BM2 -  IGNORED\n";
                                $overlap = "1";
                                last;
                        }
                        if ($ip->overlaps($ip2)==$IP_PARTIAL_OVERLAP) {
                                print LOG "$red/$BM overlaps with $red2/$BM2 -  IGNORED\n";
                                $overlap = "1";
                                last;
                        }
                        if ($ip->overlaps($ip2)==$IP_IDENTICAL) {
                                print LOG "$red/$BM overlaps with $red2/$BM2 -  IGNORED\n";
                                $overlap = "1";
                                last;
                        }
                        $k++;
                }
        } else {
                $overlap = "1";
        }
        return $overlap;
}

sub convert_mask {
	my ($network,$mask) = @_;
	my $BM;
	if ( $mask =~ /\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/ ) {
		$mask =~ /(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/;
		my $fi_oc = $1;
		my $se_oc = $2;
		my $th_oc = $3;
		my $fo_oc = $4;
 		if ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.255.252" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.255.252") { $BM = "30"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.255.248" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.255.248" ) { $BM = "29"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.255.240" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.255.240" ) { $BM = "28"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.255.224" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.255.224" ) { $BM = "27"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.255.192" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.255.192" ) { $BM = "26"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.255.128" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.255.128" ) { $BM = "25"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.255.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.255.0" ) { $BM = "24"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.254.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.254.0" ) { $BM = "23"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.252.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.252.0" ) { $BM = "22"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.248.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.248.0" ) { $BM = "21"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.240.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.240.0" ) { $BM = "20"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.224.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.224.0" ) { $BM = "19"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.192.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.192.0" ) { $BM = "18"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.128.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.128.0" ) { $BM = "17"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.255.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.255.0.0" ) { $BM = "16"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.254.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.254.0.0" ) { $BM = "15"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.252.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.252.0.0" ) { $BM = "14"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.248.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.248.0.0" ) { $BM = "13"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.240.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.240.0.0" ) { $BM = "12"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.224.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.224.0.0" ) { $BM = "11"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.192.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.192.0.0" ) { $BM = "10"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.128.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.128.0.0" ) { $BM = "9"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "255.0.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "255.0.0.0" ) { $BM = "8"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "254.0.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "254.0.0.0" ) { $BM = "7"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "252.0.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "252.0.0.0" ) { $BM = "6"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "248.0.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "248.0.0.0" ) { $BM = "5"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "240.0.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "240.0.0.0" ) { $BM = "4"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "224.0.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "224.0.0.0" ) { $BM = "3"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "192.0.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "192.0.0.0" ) { $BM = "2"; }
                elsif ( "$fi_oc.$se_oc.$th_oc.$fo_oc" eq "128.0.0.0" || "$fo_oc.$th_oc.$se_oc.$fi_oc" eq "128.0.0.0" ) { $BM = "1"; }
		elsif ( $mask eq "255.255.255.255" ) {
			print LOG "$network/$mask: HOSTROUTE - IGNORED\n";
		} else {
			print LOG "$network/$mask: Bad Netmask - IGNORED\n";
		}
	}
	return $BM;
}

#sub send_mail {
#        my $mailer = Mail::Mailer->new("");
#        $mailer->open({ From    => "$$mail_from_ref",
#                        To      => "$$mail_destinatarios_ref",
#                        Subject => "Result get_networks_snmp.pl"
#                     }) or die "error while sending mail: $!\n";
#        open (LOG_MAIL,"<$log") or die "can not open log file: $!\n";
#        while (<LOG_MAIL>) {
#                print $mailer $_;
#        }
#        print $mailer "\n\n\n\n\n\n\n\n\n--------------------------------\n\n";
#        print $mailer "This mail is automatically generated by GestioIP's get_networks_snmp.pl\n";
#        print $mailer "GestioIP (get_networks_snmp.pl)\n";
#        $mailer->close;
#        close LOG;
#}


sub insert_audit_auto {
	my ($event_class,$event_type,$event,$update_type_audit,$client_id,$user) = @_;
	my $mydatetime=time();
	my $dbh = $gip->_mysql_connection("$gip_config_file");
	my $qevent_class = $dbh->quote( $event_class );
	my $qevent_type = $dbh->quote( $event_type );
	my $qevent = $dbh->quote( $event );
	my $qupdate_type_audit = $dbh->quote( $update_type_audit );
	my $quser = $dbh->quote( $user );
	my $qmydatetime = $dbh->quote( $mydatetime );
	my $qclient_id = $dbh->quote( $client_id );
	my $sth = $dbh->prepare("INSERT INTO audit_auto (event,user,event_class,event_type,update_type_audit,date,client_id) VALUES ($qevent,$quser,$qevent_class,$event_type,$qupdate_type_audit,$qmydatetime,$qclient_id)") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement:$sth->errstr";
	$sth->finish();
}


sub get_client_id_from_name {
        my ( $client_name ) = @_;
        my $val;
	my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $qclient_name = $dbh->quote( $client_name );
        my $sth = $dbh->prepare("SELECT id FROM clients WHERE client=$qclient_name");
        $sth->execute() or  die "Can not execute statement:$sth->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_version {
        my $val;
	my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $sth = $dbh->prepare("SELECT version FROM global_config");
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_config {
        my ( $client_id ) = @_;
        my @values_config;
        my $ip_ref;
        my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("SELECT smallest_bm,max_sinc_procs,ignorar,ignore_generic_auto,generic_dyn_host_name,dyn_ranges_only,ping_timeout FROM config WHERE client_id = $qclient_id") or die ("Can not execute statement:<p>$DBI::errstr");
        $sth->execute() or die ("Can not execute statement:<p>$DBI::errstr");
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @values_config, [ @$ip_ref ];
        }
        $dbh->disconnect;
        return @values_config;
}


sub count_clients {
        my $val;
	my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $sth = $dbh->prepare("SELECT count(*) FROM clients
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub check_one_client_name {
        my ($client_name) = @_;
        my $val;
	my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $sth = $dbh->prepare("SELECT client FROM clients WHERE client=\"$client_name\"
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_client_id_one {
        my ($client_name) = @_;
        my $val;
	my $dbh = $gip->_mysql_connection("$gip_config_file");
        my $sth = $dbh->prepare("SELECT id FROM clients
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub mod_ini_stat {
        my ($new_net_count) = @_;
        my $new = "./ini_stat.html.tmp.$$";
        open(OLD, "< $ini_stat") or die "can't open $ini_stat: $!";
        open(NEW, "> $new") or die "can't open $new: $!";

        while (<OLD>) {
                if ( $_ =~ /$lang_vars{networks_found_message}: .{0,3}\d+/ ) {
                        $_ =~ /$lang_vars{networks_found_message}: .{0,3}(\d+)/;
                        my $old_net_count = $1;
                        my $net_count = $old_net_count + $new_net_count;
                        s/$lang_vars{networks_found_message}: .{0,3}\d+(<\/b>)*/$lang_vars{networks_found_message}: <b>${net_count}<\/b>/;
                }
                (print NEW $_) or die "can't write to $new: $!";
        }

        close(OLD) or die "can't close $ini_stat: $!";
        close(NEW) or die "can't close $new: $!";

        rename($new, $ini_stat) or die "can't rename $new to $ini_stat: $!";
}

sub do_term {
        print LOG "Got TERM Signal - exiting\n";
        close LOG;
        unlink("$pidfile");
        exit 3;
}


__DATA__
