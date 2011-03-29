#!/usr/bin/perl -T -w

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

# VERSION 3.0.0


use strict;
use SNMP;
use lib '../modules';
use GestioIP;
use Net::IP qw(:PROC);

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer($daten);

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

my $ip_version = $daten{'ip_version'} || "v4";
my $import_ipv4=$daten{'ipv4'} || "";
my $import_ipv6=$daten{'ipv6'} || "";

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{import_routes_message}","$vars_file");

$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (1)") if $ip_version !~ /^(v4|v6)$/;

$gip->print_error("$client_id","$$lang_vars{introduce_snmp_node_message}") if ( ! $daten{'snmp_node'} );
$gip->print_error("$client_id","$$lang_vars{node_string_too_long}") if length($daten{snmp_node}) > 75;
$gip->print_error("$client_id","$$lang_vars{introduce_community_string_message}") if ( ! $daten{'community_string'} );
$gip->print_error("$client_id","$$lang_vars{community_string_too_long}") if length($daten{community_string}) > 35 ;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (1)") if ($daten{snmp_version} !~ /^[123]$/ );

my $node=$daten{'snmp_node'};
my $community=$daten{'community_string'};

my $snmp_version=$daten{snmp_version};
my $add_comment;
$add_comment=$daten{'add_comment'} if $daten{'add_comment'};
$add_comment="n" if ! $add_comment;
my $sync=$daten{'mark_sync'} || "n";

my @config = $gip->get_config("$client_id");
my $smallest_bm = $config[0]->[0] || "22";
my $smallest_bm6 = $config[0]->[7] || "116";

my $route_proto_other="0";

my $community_type="Community";

my $auth_pass="";
my $auth_proto="";
my $auth_is_key="";
my $priv_proto="";
my $priv_pass="";
my $priv_is_key="";
my $sec_level="noAuthNoPriv";

if ( $snmp_version == "3" ) {
	$community_type = "SecName";
	$auth_proto=$daten{'auth_proto'} || "";
	$auth_pass=$daten{'auth_pass'} || "";
#	$auth_is_key=$daten{'auth_is_key'} || "";
	$priv_proto=$daten{'priv_proto'} || "";
	$priv_pass=$daten{'priv_pass'} || "";
#	$priv_is_key=$daten{'priv_is_key'} || "";
	$sec_level=$daten{'sec_level'} || "";
	$gip->print_error("$client_id","$$lang_vars{introduce_community_string_message}") if ! $community;
	$gip->print_error("$client_id","$$lang_vars{introduce_auth_pass_message}") if $auth_proto && ! $auth_pass;
	$gip->print_error("$client_id","$$lang_vars{introduce_auth_proto_message}") if $auth_pass && ! $auth_proto;
	$gip->print_error("$client_id","$$lang_vars{introduce_priv_pass_message}") if $priv_proto && ! $priv_pass;
	$gip->print_error("$client_id","$$lang_vars{introduce_priv_proto_message}") if $priv_pass && ! $priv_proto;
	$gip->print_error("$client_id","$$lang_vars{introduce_priv_auth_missing_message}") if $priv_proto && ( ! $auth_proto || ! $auth_pass );
	if ( $auth_pass ) {
		$gip->print_error("$client_id","$$lang_vars{auth_pass_characters_message}") if $auth_pass !~ /^\.{8,50}$/;
	}
	if ( $priv_pass ) {
		$gip->print_error("$client_id","$$lang_vars{priv_pass_characters_message}") if $priv_pass !~ /^\.{8,50}$/;
	}
}


if ( $ip_version eq "v4" ) {
	if ( $node !~ /^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/ ) {
		my $node_name=$node;
		my @dns_result_name=$gip->resolve_name("$client_id","$node");
		if ( ! $dns_result_name[0] ) {
			print "<p><b>$node_name</b>: $$lang_vars{host_not_found_message}<br>\n";
			print "<p><br><p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"$$lang_vars{atras_message}\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>\n";
			$gip->print_end("$client_id");
		}
	}
} else {
	my $valid_v6 = $gip->check_valid_ipv6("$node") || "0";
	$gip->print_error("$client_id","$$lang_vars{no_valid_ipv6_address_message} <b>$node</b>") if $valid_v6 != "1";
}

my $session=$gip->create_snmp_session("$client_id","$node","$community","$community_type","$snmp_version","$auth_pass","$auth_proto","$auth_is_key","$priv_proto","$priv_pass","$priv_is_key","$sec_level","$vars_file");

my ($ipRouteProto,$route_dest_cidr,$route_dest_cidr_mask,$comment);
my @route_dests_cidr;
if ( $import_ipv4 eq "ipv4" ) {

	### ipCidrRouteDest


	my $vars = new SNMP::VarList(['ipCidrRouteDest'],
				['ipCidrRouteMask'],
				['ipCidrRouteProto']);

	# get first row
	($route_dest_cidr) = $session->getnext($vars);
	my $first_query_ok = "0";
	if ($session->{ErrorStr}) {
		if ( $session->{ErrorStr} =~ /nosuchname/i ) {
	#		print "<p><br><b>$node</b>: $$lang_vars{nosuchname_snmp_error_message}\n";
		} else {
			print "<p><b>$node</b>: $$lang_vars{snmp_connect_error_message}<br>\n";
			print "<p>$session->{ErrorStr}<p><br>$$lang_vars{comprobar_host_and_community_message}<br>" if $snmp_version == 1 || $snmp_version == 2;
			print "<p><br><p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"$$lang_vars{atras_message}\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>\n";
			$gip->print_end("$client_id");
		}
	} else {
		$first_query_ok = "1";
	}

	# and all subsequent rows
	my $l = "0";
	while (!$session->{ErrorStr} and 
	       $$vars[0]->tag eq "ipCidrRouteDest"){
		($route_dest_cidr,$route_dest_cidr_mask,$ipRouteProto) = $session->getnext($vars);
		$comment = "";
		if ( $ipRouteProto =~ /local/ ) {
			$comment = "Local route from $node" if $add_comment eq "y";
		} elsif ( $ipRouteProto =~ /netmgmt/ ) {
			$comment = "Static route from $node" if $add_comment eq "y";
		} elsif ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) {
			$comment = "route from $node (proto: other)" if $add_comment eq "y";
		}
		if ( $ipRouteProto =~ /local/ || $ipRouteProto =~ /netmgmt/ || ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) ) {
			if ( $route_dest_cidr_mask =~ /\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/ ) {
				$route_dest_cidr_mask =~ /(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/;
				$route_dest_cidr_mask = $4 . "." . $3 . "." . $2 . "." . $1;
			}
			if ( $add_comment eq "y" ) {
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
	if ($session->{ErrorStr} && $first_query_ok ne "1" ) {
		if ( $session->{ErrorStr} =~ /nosuchname/i ) {
			print "<p><br><b>$node</b>: $$lang_vars{nosuchname_snmp_error_message}\n";
			print "<p><br><p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"$$lang_vars{atras_message}\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>\n";
			$gip->print_end("$client_id");
		} else {
			print "<p><b>$node</b>: $$lang_vars{snmp_connect_error_message}<br>\n";
			print "<p>$session->{ErrorStr}<p><br>$$lang_vars{comprobar_host_and_community_message}<br>" if $snmp_version == 1 || $snmp_version == 2;
			print "<p><br><p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"$$lang_vars{atras_message}\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>\n";
			$gip->print_end("$client_id");
		}
	}

	# and all subsequent rows
	while (!$session->{ErrorStr} and 
	       $$vars[0]->tag eq "ipRouteDest"){
		($route_dest,$route_mask,$route_proto) = $session->getnext($vars);
		$comment = "";
		if ( $route_proto =~ /local/ ) {
			$comment = "Local route from $node" if $add_comment eq "y";
		} elsif ( $route_proto =~ /netmgmt/ ) {
			$comment = "Static route from $node" if $add_comment eq "y";
		} elsif ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) {
			$comment = "route from $node (proto: other)" if $add_comment eq "y";
		}
		if ( $route_proto =~ /local/ || $route_proto =~ /netmgmt/ || ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) ) {
			if ( $add_comment eq "y" ) {
				$route_dests_cidr[$l] = "$route_dest/$route_mask/$comment"; 
			} else {
				$route_dests_cidr[$l] = "$route_dest/$route_mask"; 
			}
		}
		$l++;
	};
}


##### IPv6 Routes

my @route_dests_cidr_ipv6;

if ( $import_ipv6 eq "ipv6" ) {
	my $l=0;

	my @ip_arr;
	my $vb = new SNMP::Varbind();
	do {
		my $val = $session->getnext($vb);
		if ( @{$vb}[0] =~ /inetCidrRouteProto/ && @{$vb}[1] =~ /^\d{1,3}\.\d{1,3}\.((\d{1,3}\.){16})(\d{1,3})(\.\d{1,3}){16}/ ) {
			@{$vb}[1] =~ /^\d{1,3}\.\d{1,3}\.((\d{1,3}\.){16})(\d{1,3})/;
			my $ip_dec=$1;
			my $ip_mask=$3;
			my $route_proto = @{$vb}[2];

			if ( $ip_mask ne "128" ) {

				$ip_dec =~ s/\./ /g;
				@ip_arr = split(" ",$ip_dec);
				my $ipv6 = sprintf("%x%x:%x%x:%x%x:%x%x:%x%x:%x%x:%x%x:%x%x" , @ip_arr);

				$comment = "";
				if ( $route_proto =~ /local/ ) {
					$comment = "Local route from $node" if $add_comment eq "y";
				} elsif ( $route_proto =~ /netmgmt/ ) {
					$comment = "Static route from $node" if $add_comment eq "y";
				} elsif ( $ipRouteProto =~ /other/ && $route_proto_other == "1" ) {
					$comment = "route from $node (proto: other)" if $add_comment eq "y";
				}
				if ( $route_proto =~ /local/ || $route_proto =~ /netmgmt/ || ( $route_proto =~ /other/ && $route_proto_other == "1" ) ) {
					if ( $add_comment eq "y" ) {
						$route_dests_cidr_ipv6[$l] = "$ipv6/$ip_mask/$comment"; 
					} else {
						$route_dests_cidr_ipv6[$l] = "$ipv6/$ip_mask"; 
					}
				}

#				print "TEST: $ip_dec - $ipv6 - $ip_mask - $route_proto<br>\n";
				$l++;
			}


		}
	} until ($session->{ErrorNum});
}


# delete duplicated entries
my %seen = ();
my $item;
my @uniq;
foreach $item(@route_dests_cidr) {
	next if ! $item;
	push(@uniq, $item) unless $seen{$item}++;
}
@route_dests_cidr = @uniq;

my $red_num=$gip->get_last_red_num();
$red_num++;

my @overlap_redes=$gip->get_overlap_red("$ip_version","$client_id");


my ($network_cidr_mask, $network_no_cidr, $BM);

print "<span class=\"sinc_text\"><p>";

foreach $network_cidr_mask(@route_dests_cidr) {
	$ip_version = "v4";

	next if ! $network_cidr_mask;
	next if $network_cidr_mask =~ /0.0.0.0/ || $network_cidr_mask =~ /169.254.0.0/;
	$comment="";
	my ($network,$mask);
	if ( $add_comment eq "y" ) {
		($network,$mask,$comment) = split("/",$network_cidr_mask);
	} else {
		($network,$mask) = split("/",$network_cidr_mask);
	}
	# Convert netmasks to bitmasks
	$BM=$gip->convert_mask("$client_id","$network","$mask","$vars_file");
	next if ! $BM; 
	
	# check if bitmask is to small
	if ( $BM < $smallest_bm ) {
		print "<b>$network/$BM</b>: $$lang_vars{bm_not_allowed_message} $smallest_bm - $$lang_vars{ignorado_message}<br>\n";
		next;
	} 

	# Check for overlapping networks
	if ( $overlap_redes[0]->[0] ) {
		my @overlap_found = $gip->find_overlap_redes("$client_id","$network","$BM",\@overlap_redes,$ip_version,$vars_file);
		if ( $overlap_found[0] ) {
			print "<b>$network/$BM</b> $$lang_vars{overlaps_con_message} $overlap_found[0] - $$lang_vars{ignorado_message}<br>\n"; 
			next;
		}
	}

	# insert networks into the database
	print "<b>$network/$BM</b>: $$lang_vars{host_anadido_message}<br>\n";
	$red_num++;
	if ( $add_comment eq "y" ) {
		$gip->insert_net("$client_id","$red_num","$network","$BM",'','-1',"$sync","$comment",'-1',"$ip_version");
	} else {
		$gip->insert_net("$client_id","$red_num","$network","$BM",'','-1',"$sync",'','-1',"$ip_version");
	}

	my $audit_type="17";
	my $audit_class="2";
	my $update_type_audit="7";
	my $descr="---";
	$comment="---" if ! $comment;
	my $vigilada = "n";
	my $site_audit = "---";
	my $cat_audit = "---";

	my $event="$network/$BM,$descr,$site_audit,$cat_audit,$comment,$vigilada";
	$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
}

foreach $network_cidr_mask(@route_dests_cidr_ipv6) {
	$ip_version = "v6";
	
	$comment="";
	my ($network,$mask);
	if ( $add_comment eq "y" ) {
		($network,$BM,$comment) = split("/",$network_cidr_mask);
	} else {
		($network,$BM) = split("/",$network_cidr_mask);
	}

	# check if bitmask is to small
	if ( $BM < $smallest_bm6 ) {
		print "<b>$network/$BM</b>: $$lang_vars{bm_not_allowed_message} $smallest_bm6 - $$lang_vars{ignorado_message}<br>\n";
		next;
	} 

	# Check for overlapping networks
	if ( $overlap_redes[0]->[0] ) {
		my @overlap_found = $gip->find_overlap_redes("$client_id","$network","$BM",\@overlap_redes,$ip_version,$vars_file);
		if ( $overlap_found[0] ) {
			print "<b>$network/$BM</b> $$lang_vars{overlaps_con_message} $overlap_found[0] - $$lang_vars{ignorado_message}<br>\n"; 
			next;
		}
	}

	# insert networks into the database
	print "<b>$network/$BM</b>: $$lang_vars{host_anadido_message}<br>\n";
	$red_num++;
	if ( $add_comment eq "y" ) {
		$gip->insert_net("$client_id","$red_num","$network","$BM",'','-1',"$sync","$comment",'-1',"$ip_version");
	} else {
		$gip->insert_net("$client_id","$red_num","$network","$BM",'','-1',"$sync",'','-1',"$ip_version");
	}

	my $audit_type="17";
	my $audit_class="2";
	my $update_type_audit="7";
	my $descr="---";
	$comment="---" if ! $comment;
	my $vigilada = "n";
	my $site_audit = "---";
	my $cat_audit = "---";

	my $event="$network/$BM,$descr,$site_audit,$cat_audit,$comment,$vigilada";
	$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
}

print "</span>\n";

print "<h3>$$lang_vars{listo_message}</h3>\n";

$gip->print_end("$client_id");
